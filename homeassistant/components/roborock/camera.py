"""Live camera for Roborock vacuums that expose a video feed.

Signaling follows the V1 live-view protocol: the robot starts a preview,
then WebRTC offer, answer, and ICE candidates are exchanged as device
commands. Media stays between the browser and the vacuum.
"""

import asyncio
from base64 import b64decode, b64encode
from dataclasses import dataclass
import json
import logging
from typing import Any, override

from roborock.roborock_typing import RoborockCommand
from webrtc_models import RTCConfiguration, RTCIceCandidateInit, RTCIceServer

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCClientConfiguration,
    WebRTCSendMessage,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CAMERA_PIN_HASH, DOMAIN
from .coordinator import (
    RoborockConfigEntry,
    RoborockCoordinatorType,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityV1, RoborockEntityV1

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

_SDP_POLL_ATTEMPTS = 25
_SDP_POLL_DELAY = 0.25
_ICE_POLL_ATTEMPTS = 20
_ICE_POLL_DELAY = 0.25
_VIDEO_QUALITY = "HD"


def _first(response: Any) -> Any:
    """Return a single RPC result, unwrapping a one-item list."""
    if isinstance(response, list) and len(response) == 1:
        return response[0]
    return response


def _json_b64(value: Any) -> str:
    """Encode a JSON object the way the robot's signaling channel expects."""
    return b64encode(json.dumps(value).encode("utf-8")).decode("ascii")


def _decode_json(payload: str) -> Any:
    """Decode a base64 JSON signaling payload from the robot."""
    return json.loads(b64decode(payload))


@dataclass
class _CameraSession:
    """One browser session watching the vacuum camera."""

    send_message: WebRTCSendMessage
    ice_task: asyncio.Task[None] | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a camera for each vacuum that supports live video."""

    @callback
    def async_add_coordinator_entities(
        coordinator: RoborockCoordinatorType,
    ) -> None:
        """Add a camera when this vacuum reports live video support."""
        if not isinstance(coordinator, RoborockDataUpdateCoordinator):
            return
        features = coordinator.properties_api.device_features
        if getattr(features, "is_video_monitor_supported", None) is not True:
            return
        async_add_entities([RoborockCamera(coordinator)])

    for coordinator in config_entry.runtime_data.values():
        async_add_coordinator_entities(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"roborock_coordinator_added_{config_entry.entry_id}",
            async_add_coordinator_entities,
        )
    )


class RoborockCamera(RoborockCoordinatedEntityV1, Camera):
    """WebRTC camera for a Roborock vacuum."""

    _attr_translation_key = "camera"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: RoborockDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        RoborockCoordinatedEntityV1.__init__(
            self,
            unique_id=f"{coordinator.duid}_camera",
            coordinator=coordinator,
        )
        Camera.__init__(self)
        self._sessions: dict[str, _CameraSession] = {}
        self._ice_servers: list[RTCIceServer] = []

    @override
    async def send(
        self,
        command: RoborockCommand | str,
        params: dict[str, Any] | list[Any] | int | None = None,
    ) -> dict:
        """Send a command without refreshing the coordinator.

        Signaling polls SDP and ICE many times a second. A coordinator refresh
        on each poll would stall the stream.
        """
        return await RoborockEntityV1.send(self, command, params)

    @override
    async def async_added_to_hass(self) -> None:
        """Fetch TURN credentials so the first viewer can relay media."""
        await super().async_added_to_hass()
        await self._async_refresh_turn()

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return no snapshot.

        The vacuum camera is a live WebRTC feed and does not provide a still.
        """
        return None

    @callback
    @override
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return cached TURN servers from the vacuum."""
        return WebRTCClientConfiguration(
            configuration=RTCConfiguration(list(self._ice_servers))
        )

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Start a preview and return the vacuum's SDP answer."""
        pin_hash = self.coordinator.config_entry.options.get(CONF_CAMERA_PIN_HASH)
        if not isinstance(pin_hash, str) or not pin_hash:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="camera_pin_required",
            )

        for old_session_id in list(self._sessions):
            await self._drop_session(old_session_id, stop_preview=True)

        started = False
        try:
            await self.send(
                RoborockCommand.CHECK_HOMESEC_PASSWORD,
                {"password": pin_hash},
            )
            await self.send(
                RoborockCommand.SWITCH_VIDEO_QUALITY,
                {"quality": _VIDEO_QUALITY},
            )
            await self.send(
                RoborockCommand.START_CAMERA_PREVIEW,
                {
                    "client_id": session_id,
                    "quality": _VIDEO_QUALITY,
                    "password": pin_hash,
                },
            )
            started = True
            answer = await self._poll_sdp_answer()
        except HomeAssistantError:
            if started:
                await self._stop_preview()
            raise

        session = _CameraSession(send_message)
        self._sessions[session_id] = session
        send_message(WebRTCAnswer(answer))
        session.ice_task = self.hass.async_create_task(
            self._poll_remote_ice(session_id)
        )
        self._attr_is_streaming = True
        self.async_write_ha_state()

    @override
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Forward a browser ICE candidate to the vacuum."""
        if session_id not in self._sessions:
            return
        await self.send(
            RoborockCommand.SEND_ICE_TO_ROBOT,
            {
                "app_ice": _json_b64(
                    {
                        "candidate": candidate.candidate,
                        "sdpMid": candidate.sdp_mid,
                        "sdpMLineIndex": candidate.sdp_m_line_index,
                    }
                )
            },
        )

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Stop the preview when the browser leaves."""
        if session_id not in self._sessions:
            return
        self.hass.async_create_task(self._drop_session(session_id, stop_preview=True))

    async def _async_refresh_turn(self) -> None:
        """Cache ephemeral TURN credentials advertised by the vacuum."""
        try:
            payload = _first(await self.send(RoborockCommand.GET_TURN_SERVER))
        except HomeAssistantError:
            _LOGGER.debug("Vacuum did not provide TURN credentials", exc_info=True)
            return
        if not isinstance(payload, dict):
            return
        url = payload.get("url")
        if not isinstance(url, str) or not url:
            return
        username = payload.get("user")
        credential = payload.get("pwd")
        self._ice_servers = [
            RTCIceServer(
                url,
                username if isinstance(username, str) else None,
                credential if isinstance(credential, str) else None,
            )
        ]

    async def _poll_sdp_answer(self) -> str:
        """Poll until the vacuum returns its SDP answer."""
        for _ in range(_SDP_POLL_ATTEMPTS):
            payload = _first(await self.send(RoborockCommand.GET_DEVICE_SDP))
            dev_sdp = payload.get("dev_sdp") if isinstance(payload, dict) else None
            if isinstance(dev_sdp, str) and dev_sdp != "retry":
                decoded = _decode_json(dev_sdp)
                if isinstance(decoded, dict) and isinstance(decoded.get("sdp"), str):
                    return decoded["sdp"]
            await asyncio.sleep(_SDP_POLL_DELAY)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="camera_answer_timeout",
        )

    async def _poll_remote_ice(self, session_id: str) -> None:
        """Forward ICE candidates produced by the vacuum."""
        seen: set[str] = set()
        try:
            for _ in range(_ICE_POLL_ATTEMPTS):
                session = self._sessions.get(session_id)
                if session is None:
                    return
                payload = _first(await self.send(RoborockCommand.GET_DEVICE_ICE))
                encoded_candidates = (
                    payload.get("dev_ice") if isinstance(payload, dict) else None
                )
                if isinstance(encoded_candidates, list):
                    for encoded in encoded_candidates:
                        if not isinstance(encoded, str) or encoded in seen:
                            continue
                        seen.add(encoded)
                        self._forward_remote_candidate(session, encoded)
                await asyncio.sleep(_ICE_POLL_DELAY)
        except asyncio.CancelledError:
            raise
        except HomeAssistantError:
            _LOGGER.debug("Stopped reading vacuum ICE candidates", exc_info=True)

    def _forward_remote_candidate(self, session: _CameraSession, encoded: str) -> None:
        """Send one vacuum ICE candidate to the browser."""
        try:
            ice = _decode_json(encoded)
        except ValueError, json.JSONDecodeError:
            return
        if not isinstance(ice, dict):
            return
        candidate = ice.get("candidate")
        if not isinstance(candidate, str):
            return
        sdp_m_line_index = ice.get("sdpMLineIndex")
        init_kwargs: dict[str, Any] = {
            "sdp_m_line_index": (
                sdp_m_line_index if isinstance(sdp_m_line_index, int) else 0
            )
        }
        if isinstance(sdp_mid := ice.get("sdpMid"), str):
            init_kwargs["sdp_mid"] = sdp_mid
        session.send_message(
            WebRTCCandidate(RTCIceCandidateInit(candidate, **init_kwargs))
        )

    async def _drop_session(self, session_id: str, *, stop_preview: bool) -> None:
        """Forget a browser session and optionally power the camera down."""
        session = self._sessions.pop(session_id, None)
        if session is not None and session.ice_task is not None:
            session.ice_task.cancel()
        if self._sessions:
            return
        self._attr_is_streaming = False
        self.async_write_ha_state()
        if stop_preview:
            await self._stop_preview()

    async def _stop_preview(self) -> None:
        """Release the vacuum's single camera session."""
        try:
            await self.send(RoborockCommand.STOP_CAMERA_PREVIEW, [])
        except HomeAssistantError:
            _LOGGER.debug("Unable to stop the vacuum camera preview", exc_info=True)
