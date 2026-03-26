"""Support for Abode Security System cameras."""

from __future__ import annotations

import asyncio
import base64
import binascii
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import json
import time
from typing import Any, cast

from aiohttp import ClientError, ClientWebSocketResponse, WSMessage, WSMsgType
from jaraco.abode.devices.base import Device
from jaraco.abode.devices.camera import Camera as AbodeCam
from jaraco.abode.exceptions import Exception as AbodeException
from jaraco.abode.helpers import timeline
import requests
from requests.models import Response
from webrtc_models import RTCConfiguration, RTCIceServer

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    RTCIceCandidateInit,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCClientConfiguration,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle

from . import AbodeSystem
from .const import DOMAIN_DATA, LOGGER
from .entity import AbodeDevice

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=90)
SNAPSHOT_CAMERA_TYPE_TAGS: set[str] = {
    "device_type.mini_cam",
    "device_type.doorbell",
    "device_type.abode_cam_3",
}
MEDIA_PLAYBACK_URL = "/integrations/v1/media/getPlaybackUrl"
KVS_STREAM_URL = "/integrations/v1/camera/{camera_id}/kvs/stream"
KVS_SIGNALING_ACTION_SDP_OFFER = "SDP_OFFER"
KVS_SIGNALING_ACTION_ICE_CANDIDATE = "ICE_CANDIDATE"
KVS_SIGNALING_CACHE_SECONDS = 240


@dataclass(slots=True)
class _AbodeWebRTCSession:
    """Track an active Abode WebRTC signaling session."""

    ws: ClientWebSocketResponse
    listener_task: asyncio.Task[None] | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Abode camera devices."""
    data = hass.data[DOMAIN_DATA]

    async_add_entities(
        AbodeCamera(data, device, timeline.CAPTURE_IMAGE)
        for device in data.abode.get_devices(generic_type="camera")
    )


class AbodeCamera(AbodeDevice, Camera):
    """Representation of an Abode camera."""

    _device: AbodeCam
    _attr_name = None

    def __init__(self, data: AbodeSystem, device: Device, event: Event) -> None:
        """Initialize the Abode device."""
        AbodeDevice.__init__(self, data, device)
        Camera.__init__(self)
        self._event = event
        self._response: Response | None = None
        type_tag = str(getattr(device, "type_tag", "")).lower()
        self._supports_snapshot = bool(getattr(device, "is_new_camera", False)) or (
            type_tag in SNAPSHOT_CAMERA_TYPE_TAGS
        )
        self._snapshot_image: bytes | None = None
        self._webrtc_ice_servers: list[RTCIceServer] = []
        self._kvs_channel_endpoint: str | None = None
        self._kvs_signaling_last_refresh_monotonic = 0.0
        self._webrtc_sessions: dict[str, _AbodeWebRTCSession] = {}
        if self._supports_snapshot:
            self._attr_supported_features |= CameraEntityFeature.STREAM

    async def async_added_to_hass(self) -> None:
        """Subscribe Abode events."""
        await super().async_added_to_hass()

        self.hass.async_add_executor_job(
            self._data.abode.events.add_timeline_callback,
            self._event,
            self._capture_callback,
        )

        signal = f"abode_camera_capture_{self.entity_id}"
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, self.capture))
        if self._supports_snapshot:
            self.hass.async_create_task(self._async_refresh_kvs_signaling_info())

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup active WebRTC sessions."""
        await super().async_will_remove_from_hass()
        await asyncio.gather(
            *(
                self._async_close_webrtc_session(session_id)
                for session_id in list(self._webrtc_sessions)
            ),
            return_exceptions=True,
        )

    def capture(self) -> bool:
        """Request a new image capture."""
        return cast(bool, self._device.capture())

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_image(self) -> None:
        """Find a new image on the timeline."""
        if self._supports_snapshot and self._refresh_snapshot_image():
            return

        try:
            if self._device.refresh_image():
                self.get_image()
        except AbodeException as err:
            LOGGER.warning("Failed to refresh camera image: %s", err)

    def _refresh_snapshot_image(self) -> bool:
        """Attempt to refresh image using Abode snapshot endpoint."""
        try:
            if not self._device.snapshot():
                LOGGER.debug("Camera snapshot request did not return image data")
                return False
        except AbodeException as err:
            LOGGER.warning("Failed to refresh camera snapshot image: %s", err)
            return False

        snapshot_data_url = self._device.snapshot_data_url(get_snapshot=False)
        _, separator, encoded_snapshot = snapshot_data_url.partition(",")
        if not separator:
            LOGGER.warning(
                "Failed to decode camera snapshot: unexpected snapshot format"
            )
            return False

        try:
            self._snapshot_image = base64.b64decode(encoded_snapshot)
        except (binascii.Error, ValueError) as err:
            LOGGER.warning("Failed to decode camera snapshot: %s", err)
            return False

        return True

    def get_image(self) -> None:
        """Attempt to download the most recent capture."""
        if self._device.image_url:
            try:
                self._response = requests.get(
                    self._device.image_url, stream=True, timeout=10
                )

                self._response.raise_for_status()
            except requests.HTTPError as err:
                LOGGER.warning("Failed to get camera image: %s", err)
                self._response = None
        else:
            self._response = None

    def _get_stream_source(self) -> str | None:
        """Get an HLS stream source URL for cameras supporting KVS playback."""
        stream_request_payload = {
            "cameraId": self._device.id,
            "startTime": int(time.time()) - 30,
            "format": "hls",
            "playbackMode": "LIVE_REPLAY",
        }
        try:
            response = self._data.abode.send_request(
                "post", MEDIA_PLAYBACK_URL, data=stream_request_payload
            )
        except AbodeException as err:
            LOGGER.warning("Failed to get camera stream URL: %s", err)
            return None

        playback_url = response.json().get("playbackUrl")
        if not playback_url:
            LOGGER.warning("Failed to get camera stream URL: missing playbackUrl")
            return None

        LOGGER.debug("Fetched camera stream URL for camera %s", self._device.id)
        return str(playback_url)

    async def stream_source(self) -> str | None:
        """Get the source of the stream."""
        if not self._supports_snapshot:
            return None

        return await self.hass.async_add_executor_job(self._get_stream_source)

    def _get_kvs_signaling_info(self) -> dict[str, Any]:
        """Get KVS signaling metadata for the camera."""
        response = self._data.abode.send_request(
            "post", KVS_STREAM_URL.format(camera_id=self._device.id)
        )
        raw_signaling_info = response.json()
        if not isinstance(raw_signaling_info, dict):
            raise HomeAssistantError("Invalid KVS signaling response")
        signaling_info = raw_signaling_info
        channel_endpoint = signaling_info.get("channelEndpoint")
        if not isinstance(channel_endpoint, str) or not channel_endpoint:
            raise HomeAssistantError("Missing KVS channel endpoint")

        self._kvs_channel_endpoint = channel_endpoint
        self._webrtc_ice_servers = self._parse_ice_servers(
            signaling_info.get("iceServers", [])
        )
        self._kvs_signaling_last_refresh_monotonic = time.monotonic()
        return signaling_info

    def _kvs_signaling_is_fresh(self) -> bool:
        """Return whether cached KVS signaling metadata is still fresh."""
        if not self._kvs_channel_endpoint:
            return False
        return (
            time.monotonic() - self._kvs_signaling_last_refresh_monotonic
        ) < KVS_SIGNALING_CACHE_SECONDS

    async def _async_refresh_kvs_signaling_info(
        self, *, force: bool = False
    ) -> dict[str, Any] | None:
        """Refresh cached KVS signaling metadata."""
        if not force and self._kvs_signaling_is_fresh():
            return {
                "channelEndpoint": self._kvs_channel_endpoint,
                "iceServers": [server.to_dict() for server in self._webrtc_ice_servers],
            }
        try:
            return await self.hass.async_add_executor_job(self._get_kvs_signaling_info)
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Failed to refresh Abode KVS signaling info: %s", err)
            return None

    @staticmethod
    def _parse_ice_servers(raw_ice_servers: Any) -> list[RTCIceServer]:
        """Parse Abode KVS ICE servers into WebRTC model objects."""
        if not isinstance(raw_ice_servers, list):
            return []

        ice_servers: list[RTCIceServer] = []
        for raw_server in raw_ice_servers:
            if not isinstance(raw_server, dict):
                continue
            urls = raw_server.get("urls")
            if not isinstance(urls, (str, list)):
                continue
            username = raw_server.get("username")
            credential = raw_server.get("credential")
            ice_servers.append(
                RTCIceServer(
                    urls=urls,
                    username=username if isinstance(username, str) else None,
                    credential=credential if isinstance(credential, str) else None,
                )
            )

        return ice_servers

    @staticmethod
    def _build_signaling_message(
        action: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Build a KVS signaling message."""
        encoded_payload = base64.b64encode(json.dumps(payload).encode()).decode()
        return {
            "action": action,
            "messagePayload": encoded_payload,
        }

    @staticmethod
    def _decode_signaling_message(msg: WSMessage) -> tuple[str, dict[str, Any]] | None:
        """Decode a signaling message from KVS."""
        try:
            message_data = json.loads(msg.data)
        except TypeError, json.JSONDecodeError:
            return None

        if not isinstance(message_data, dict):
            return None

        message_type = message_data.get("messageType")
        encoded_payload = message_data.get("messagePayload")
        if not isinstance(message_type, str) or not isinstance(encoded_payload, str):
            return None

        try:
            payload = json.loads(base64.b64decode(encoded_payload))
        except TypeError, ValueError, binascii.Error, json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        return message_type, payload

    @staticmethod
    def _parse_remote_ice_candidate(
        payload: dict[str, Any],
    ) -> RTCIceCandidateInit | None:
        """Parse a remote ICE candidate payload."""
        try:
            return RTCIceCandidateInit.from_dict(payload)
        except TypeError, ValueError:
            candidate = payload.get("candidate")
            if not isinstance(candidate, str):
                return None
            sdp_mid = payload.get("sdpMid")
            sdp_m_line_index = payload.get("sdpMLineIndex")
            sdp_m_line_index_int: int | None
            if isinstance(sdp_m_line_index, int):
                sdp_m_line_index_int = sdp_m_line_index
            elif isinstance(sdp_m_line_index, str):
                try:
                    sdp_m_line_index_int = int(sdp_m_line_index)
                except TypeError, ValueError:
                    sdp_m_line_index_int = None
            else:
                sdp_m_line_index_int = None
            return RTCIceCandidateInit(
                candidate,
                sdp_mid=sdp_mid if isinstance(sdp_mid, str) else None,
                sdp_m_line_index=sdp_m_line_index_int,
            )

    async def _async_listen_webrtc_messages(
        self,
        session_id: str,
        ws: ClientWebSocketResponse,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Listen for KVS signaling messages for a session."""
        try:
            while True:
                msg = await ws.receive()
                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                    break
                if msg.type is WSMsgType.ERROR:
                    error = ws.exception()
                    send_message(
                        WebRTCError(
                            "webrtc_signaling_error",
                            str(error) if error else "Unknown signaling error",
                        )
                    )
                    break
                if msg.type is not WSMsgType.TEXT:
                    continue

                if not (decoded := self._decode_signaling_message(msg)):
                    continue

                message_type, payload = decoded
                if message_type == "SDP_ANSWER":
                    sdp = payload.get("sdp")
                    if isinstance(sdp, str):
                        LOGGER.debug(
                            "Received WebRTC SDP answer for camera %s session %s",
                            self._device.id,
                            session_id,
                        )
                        send_message(WebRTCAnswer(sdp))
                elif message_type == "ICE_CANDIDATE":
                    if candidate := self._parse_remote_ice_candidate(payload):
                        LOGGER.debug(
                            "Received remote WebRTC ICE candidate for camera %s session %s",
                            self._device.id,
                            session_id,
                        )
                        send_message(WebRTCCandidate(candidate))
        finally:
            await self._async_close_webrtc_session(session_id, cancel_listener=False)

    async def _async_close_webrtc_session(
        self, session_id: str, *, cancel_listener: bool = True
    ) -> None:
        """Close and cleanup a WebRTC session."""
        if not (session := self._webrtc_sessions.pop(session_id, None)):
            return

        if (
            cancel_listener
            and session.listener_task
            and not session.listener_task.done()
        ):
            session.listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await session.listener_task

        if not session.ws.closed:
            await session.ws.close()

    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return WebRTC client configuration for Abode cameras."""
        return WebRTCClientConfiguration(
            configuration=RTCConfiguration(ice_servers=self._webrtc_ice_servers.copy())
        )

    async def async_handle_async_webrtc_offer(
        self,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle an incoming WebRTC offer from the frontend."""
        if not self._supports_snapshot:
            raise HomeAssistantError("Camera does not support WebRTC")

        if (
            not self._kvs_signaling_is_fresh()
            and (await self._async_refresh_kvs_signaling_info()) is None
            and not self._kvs_channel_endpoint
        ):
            raise HomeAssistantError("Failed to refresh Abode WebRTC signaling info")

        if not self._kvs_channel_endpoint:
            raise HomeAssistantError("Missing Abode WebRTC channel endpoint")

        client_session = async_get_clientsession(self.hass)
        LOGGER.debug(
            "Opening Abode WebRTC signaling websocket for camera %s",
            self._device.id,
        )
        try:
            ws = await client_session.ws_connect(self._kvs_channel_endpoint)
        except ClientError as err:
            raise HomeAssistantError(
                "Failed to connect to Abode WebRTC signaling endpoint"
            ) from err

        webrtc_session = _AbodeWebRTCSession(ws=ws)
        self._webrtc_sessions[session_id] = webrtc_session
        webrtc_session.listener_task = self.hass.async_create_task(
            self._async_listen_webrtc_messages(session_id, ws, send_message)
        )

        try:
            await ws.send_json(
                self._build_signaling_message(
                    KVS_SIGNALING_ACTION_SDP_OFFER,
                    {"type": "offer", "sdp": offer_sdp},
                )
            )
            LOGGER.debug(
                "Sent WebRTC SDP offer for camera %s session %s",
                self._device.id,
                session_id,
            )
        except ClientError as err:
            await self._async_close_webrtc_session(session_id)
            raise HomeAssistantError("Failed to send WebRTC offer") from err

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a local WebRTC candidate from the frontend."""
        if not (session := self._webrtc_sessions.get(session_id)):
            LOGGER.debug(
                "Ignoring local WebRTC ICE candidate for unknown session %s camera %s",
                session_id,
                self._device.id,
            )
            return

        try:
            await session.ws.send_json(
                self._build_signaling_message(
                    KVS_SIGNALING_ACTION_ICE_CANDIDATE, candidate.to_dict()
                )
            )
            LOGGER.debug(
                "Sent local WebRTC ICE candidate for camera %s session %s",
                self._device.id,
                session_id,
            )
        except ClientError as err:
            raise HomeAssistantError("Failed to send WebRTC candidate") from err

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        self.hass.async_create_task(self._async_close_webrtc_session(session_id))

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get a camera image."""
        self.refresh_image()

        if self._snapshot_image:
            return self._snapshot_image

        if self._response:
            return self._response.content

        return None

    def turn_on(self) -> None:
        """Turn on camera."""
        self._device.privacy_mode(False)

    def turn_off(self) -> None:
        """Turn off camera."""
        self._device.privacy_mode(True)

    def _capture_callback(self, capture: Any) -> None:
        """Update the image with the device then refresh device."""
        self._device.update_image_location(capture)
        self.get_image()
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return cast(bool, self._device.is_on)
