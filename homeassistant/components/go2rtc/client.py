"""The go2rtc component."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from go2rtc_client.ws import (
    Go2RtcWsClient,
    ReceiveMessages,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WsError,
)
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera.webrtc import (
    WebRTCAnswer as HAWebRTCAnswer,
    WebRTCCandidate as HAWebRTCCandidate,
    WebRTCError,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import Go2RtcData

if TYPE_CHECKING:
    from homeassistant.components.camera import Camera, WebRTCMessage, WebRTCSendMessage

_LOGGER = logging.getLogger(__name__)


class Go2RtcClient:
    """Go2rtc client."""

    def __init__(
        self,
        hass: HomeAssistant,
        data: Go2RtcData,
        camera: Camera,
        client_remove_fn: Callable[[], None],
    ) -> None:
        """Initialize the Go2rtc client."""
        self._hass = hass
        data.ha_clients.append(self)
        self._data = data
        self._camera = camera
        self._sessions: dict[str, Go2RtcWsClient] = {}
        self._client_remove_fn = client_remove_fn

    async def _update_stream_source(self, camera: Camera) -> None:
        """Update the stream source in go2rtc config if needed."""
        if not (stream_source := await camera.stream_source()):
            raise HomeAssistantError("Camera has no stream source")

        streams = await self._data.rest_client.streams.list()

        if (stream := streams.get(camera.entity_id)) is None or not any(
            stream_source == producer.url for producer in stream.producers
        ):
            await self._data.rest_client.streams.add(
                camera.entity_id,
                [
                    stream_source,
                    # We are setting any ffmpeg rtsp related logs to debug
                    # Connection problems to the camera will be logged by the first stream
                    # Therefore setting it to debug will not hide any important logs
                    f"ffmpeg:{camera.entity_id}#audio=opus#query=log_level=debug",
                    f"ffmpeg:{camera.entity_id}#video=mjpeg",
                ],
            )

    async def async_handle_async_webrtc_offer(
        self,
        camera: Camera,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle the WebRTC offer and return the answer via the provided callback."""
        self._sessions[session_id] = ws_client = Go2RtcWsClient(
            self._data.session, self._data.url, source=camera.entity_id
        )

        try:
            await self._update_stream_source(camera)
        except HomeAssistantError as err:
            send_message(WebRTCError("go2rtc_webrtc_offer_failed", str(err)))
            return

        @callback
        def on_messages(message: ReceiveMessages) -> None:
            """Handle messages."""
            value: WebRTCMessage
            match message:
                case WebRTCCandidate():
                    value = HAWebRTCCandidate(RTCIceCandidateInit(message.candidate))
                case WebRTCAnswer():
                    value = HAWebRTCAnswer(message.sdp)
                case WsError():
                    value = WebRTCError("go2rtc_webrtc_offer_failed", message.error)

            send_message(value)

        ws_client.subscribe(on_messages)
        config = camera.async_get_webrtc_client_configuration()
        await ws_client.send(WebRTCOffer(offer_sdp, config.configuration.ice_servers))

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle the WebRTC candidate."""

        if ws_client := self._sessions.get(session_id):
            await ws_client.send(WebRTCCandidate(candidate.candidate))
        else:
            _LOGGER.debug("Unknown session %s. Ignoring candidate", session_id)

    @callback
    def async_close_session(self, session_id: str) -> None:
        """Close the session."""
        ws_client = self._sessions.pop(session_id)
        self._hass.async_create_task(ws_client.close())

    async def async_get_image(
        self,
        camera: Camera,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Get an image from the camera."""
        await self._update_stream_source(camera)
        return await self._data.rest_client.get_jpeg_snapshot(
            camera.entity_id, width, height
        )

    async def teardown(self) -> None:
        """Tear down the client."""
        for ws_client in self._sessions.values():
            await ws_client.close()
        self._sessions.clear()
        self._data.ha_clients.remove(self)
        self._client_remove_fn()
