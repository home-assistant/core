"""Support for Litter-Robot cameras."""

import asyncio
import functools
import logging
from pathlib import Path
from typing import Any, override

from aiohttp import ClientError
from pylitterbot import LitterRobot5
from pylitterbot.camera import CameraSession, CameraSignalingRelay
from pylitterbot.exceptions import LitterRobotException
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

from .const import DOMAIN
from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

PLACEHOLDER = Path(__file__).parent / "placeholder.png"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cameras using config entry."""
    coordinator = entry.runtime_data
    known_robots: set[str] = set()

    def _check_robots() -> None:
        new_robots = [
            robot
            for robot in coordinator.account.robots
            if isinstance(robot, LitterRobot5)
            and robot.has_camera
            and robot.serial not in known_robots
        ]
        if new_robots:
            known_robots.update(robot.serial for robot in new_robots)
            async_add_entities(
                LitterRobotCameraEntity(robot=robot, coordinator=coordinator)
                for robot in new_robots
            )

    _check_robots()
    entry.async_on_unload(coordinator.async_add_listener(_check_robots))


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
            else:
                # copy: the STUN url appended below must not be pushed onto
                # the cached session's own list, which is reused per offer
                turn_urls = list(turn_urls)
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
    _attr_is_streaming = False
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
        self._refreshing = False
        # the placeholder returned by async_camera_image is a PNG, not the
        # jpeg the base class assumes
        self.content_type = "image/png"

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a placeholder image.

        The device streams over WebRTC and has no snapshot endpoint. Returning
        None would make every thumbnail request raise "Unable to get image",
        so a placeholder is served instead, as other WebRTC-only cameras do.
        """
        return await self.hass.async_add_executor_job(self.placeholder_image)

    @classmethod
    @functools.cache
    def placeholder_image(cls) -> bytes:
        """Return the placeholder image used when no still is available."""
        return PLACEHOLDER.read_bytes()

    @override
    async def async_added_to_hass(self) -> None:
        """Fetch a first session for TURN credentials when added to hass.

        It is not renewed afterwards, see `_refresh_cached_session`.
        """
        await super().async_added_to_hass()
        await self._refresh_cached_session()

    async def _refresh_cached_session(self) -> None:
        """Fetch a camera session to get TURN credentials for viewers.

        Sessions are short-lived, so they are fetched when a viewer asks for
        its configuration and none is usable, rather than renewed ahead of
        time: renewing in the background would create a session every few
        minutes for a camera nobody is watching. Failures are logged at debug
        level and the cache is left empty, so the next request tries again.
        """
        if self._refreshing:
            return
        self._refreshing = True
        try:
            client = self.robot.get_camera_client()
            # Use auto_start=False — we only need TURN credentials here,
            # not to wake the camera for a stream.
            self._cached_session = await client.generate_session(auto_start=False)
            _LOGGER.debug(
                "Camera session refreshed (expires %s)",
                self._cached_session.session_expiration,
            )
        except LitterRobotException, ClientError, TimeoutError:
            _LOGGER.debug("Failed to refresh camera session", exc_info=True)
        finally:
            self._refreshing = False

    @callback
    @override
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration with TURN servers."""
        session = self._cached_session
        if session is None or (
            (expires := session.session_expiration) is not None
            and expires <= dt_util.utcnow()
        ):
            # nothing usable: withhold stale credentials and fetch a
            # replacement now. This call cannot wait for it (it is a
            # synchronous callback), so this client gets no TURN servers and
            # the next one gets the new credentials.
            if session is not None:
                _LOGGER.debug("Camera session expired, fetching a new one")
            session = None
            self._cached_session = None
            self.hass.async_create_task(self._refresh_cached_session())
        ice_servers = _build_ice_servers(session) if session else []
        if not ice_servers:
            _LOGGER.debug("Serving the WebRTC configuration without TURN servers")
        return WebRTCClientConfiguration(
            configuration=RTCConfiguration(ice_servers=ice_servers),
        )

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle a WebRTC offer by relaying signaling to the camera."""
        try:
            client = self.robot.get_camera_client()
        except LitterRobotException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="camera_not_available",
                translation_placeholders={"error": str(err)},
            ) from err

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
        except asyncio.CancelledError:
            # the client went away mid-offer
            self._relays.pop(session_id, None)
            raise
        except (LitterRobotException, ClientError, TimeoutError) as err:
            self._relays.pop(session_id, None)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="camera_stream_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if self._relays.get(session_id) is not relay:
            # the viewer went away while start() was connecting, and the
            # teardown has already run: nothing owns this relay any more
            await relay.close()
            return

        # keep the session the relay started with; the next viewer reuses its
        # TURN credentials until it expires
        self._cached_session = session
        self._attr_is_streaming = True
        self.async_write_ha_state()
        _LOGGER.debug("Started WebRTC session %s", session_id)

    @override
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
            # ordinary during teardown: candidates can arrive after close
            _LOGGER.debug("No relay found for session %s", session_id)

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        if relay := self._relays.pop(session_id, None):
            _LOGGER.debug("Closing WebRTC session %s", session_id)
            self.hass.async_create_task(relay.close())
            self._update_streaming()
        super().close_webrtc_session(session_id)

    async def _async_close_relay(self, session_id: str) -> None:
        """Close a WebRTC session, awaiting the relay teardown.

        Used when the entity is removed, where a scheduled task may never run.
        """
        if relay := self._relays.pop(session_id, None):
            _LOGGER.debug("Closing WebRTC session %s", session_id)
            await relay.close()
            self._update_streaming()
        super().close_webrtc_session(session_id)

    def _update_streaming(self) -> None:
        """Report streaming only while a viewer is connected."""
        self._attr_is_streaming = bool(self._relays)
        self.async_write_ha_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Close all active relays when the entity is removed."""
        for session_id in list(self._relays):
            # awaited, not fire-and-forget
            await self._async_close_relay(session_id)
        await super().async_will_remove_from_hass()
