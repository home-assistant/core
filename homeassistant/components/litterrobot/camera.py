"""Support for Litter-Robot cameras."""

from __future__ import annotations

import logging
from typing import Any

from pylitterbot import LitterRobot5
from pylitterbot.camera import CameraSession, CameraSignalingRelay
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
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cameras using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotCameraEntity(robot=robot, coordinator=coordinator)
        for robot in coordinator.account.robots
        if isinstance(robot, LitterRobot5) and robot.has_camera
    )


def _build_ice_servers(session: CameraSession) -> list[RTCIceServer]:
    """Build RTCIceServer list from a camera session's TURN credentials."""
    servers: list[RTCIceServer] = []
    for cred in session.turn_servers:
        # Handle both formats:
        # Standard: {"urls": [...], "username": "...", "credential": "..."}
        # Watford:  {"turnUrl": [...], "stunUrl": "...", "username": "...", "password": "..."}
        urls = cred.get("urls") or cred.get("uris") or []
        if isinstance(urls, str):
            urls = [urls]
        if not urls:
            turn_urls = cred.get("turnUrl") or []
            if isinstance(turn_urls, str):
                turn_urls = [turn_urls]
            stun_url = cred.get("stunUrl")
            if stun_url:
                turn_urls.append(stun_url)
            urls = turn_urls
        if urls:
            servers.append(
                RTCIceServer(
                    urls=urls,
                    username=cred.get("username", ""),
                    credential=cred.get("credential") or cred.get("password", ""),
                )
            )
    return servers


class LitterRobotCameraEntity(LitterRobotEntity[LitterRobot5], Camera):
    """Litter-Robot camera entity with WebRTC support."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_is_streaming = True
    _attr_translation_key = "camera"

    def __init__(
        self,
        robot: LitterRobot5,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the camera entity."""
        super().__init__(
            robot,
            coordinator,
            EntityDescription(key="camera"),
        )
        Camera.__init__(self)
        self._relays: dict[str, CameraSignalingRelay] = {}
        self._cached_session: CameraSession | None = None

    async def async_added_to_hass(self) -> None:
        """Pre-cache a session for TURN credentials when added to hass."""
        await super().async_added_to_hass()
        await self._refresh_cached_session()

    async def _refresh_cached_session(self) -> None:
        """Fetch a fresh camera session to keep TURN credentials current."""
        try:
            client = self.robot.get_camera_client()
            # Use auto_start=False — we only need TURN credentials here,
            # not to wake the camera for a stream.
            self._cached_session = await client.generate_session(auto_start=False)
            _LOGGER.debug(
                "Camera session refreshed (expires %s)",
                self._cached_session.session_expiration,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to refresh camera session", exc_info=True)

    @callback
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration with TURN servers."""
        session = self._cached_session
        if session and session.session_expiration:
            if session.session_expiration <= dt_util.utcnow():
                _LOGGER.debug("Camera session expired, will refresh in background")
                session = None
                self.hass.async_create_task(self._refresh_cached_session())
        ice_servers = _build_ice_servers(session) if session else []
        return WebRTCClientConfiguration(
            configuration=RTCConfiguration(ice_servers=ice_servers),
        )

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle a WebRTC offer by relaying signaling to the camera."""
        try:
            client = self.robot.get_camera_client()
        except Exception as err:
            raise HomeAssistantError(f"Camera not available: {err}") from err

        relay = CameraSignalingRelay(client)
        # Store relay immediately so ICE candidates arriving before start()
        # completes can be buffered by the relay.
        self._relays[session_id] = relay

        @callback
        def on_answer(answer_sdp: str) -> None:
            """Forward the SDP answer to the browser."""
            send_message(WebRTCAnswer(answer=answer_sdp))

        @callback
        def on_candidate(candidate: dict[str, Any]) -> None:
            """Forward ICE candidates to the browser."""
            send_message(
                WebRTCCandidate(
                    RTCIceCandidateInit(
                        candidate=candidate.get("candidate", ""),
                        sdp_mid=candidate.get("sdpMid", "0"),
                        sdp_m_line_index=candidate.get("sdpMLineIndex", 0),
                    )
                )
            )

        try:
            session = await relay.start(offer_sdp, on_answer, on_candidate)
        except Exception as err:
            self._relays.pop(session_id, None)
            raise HomeAssistantError(f"Failed to start camera stream: {err}") from err

        # Update cached session for fresh TURN creds
        self._cached_session = session
        _LOGGER.debug("Started WebRTC session %s", session_id)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Forward a browser ICE candidate to the camera."""
        if relay := self._relays.get(session_id):
            await relay.send_candidate(
                {
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdp_mid or "0",
                    "sdpMLineIndex": candidate.sdp_m_line_index or 0,
                }
            )
        else:
            _LOGGER.warning("No relay found for session %s", session_id)

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        if relay := self._relays.pop(session_id, None):
            _LOGGER.debug("Closing WebRTC session %s", session_id)
            self.hass.async_create_task(relay.close())
        super().close_webrtc_session(session_id)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the latest video thumbnail as a camera image."""
        return self.coordinator.camera_thumbnails.get(self.robot.serial)

    async def async_will_remove_from_hass(self) -> None:
        """Close all active relays when the entity is removed."""
        for session_id in list(self._relays):
            self.close_webrtc_session(session_id)
        await super().async_will_remove_from_hass()
