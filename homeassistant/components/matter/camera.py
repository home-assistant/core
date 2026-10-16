"""Matter camera platform."""

from base64 import b64decode
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, override

from chip.clusters.Objects import CameraAvStreamManagement, WebRtcTransportProvider
from matter_server.client.exceptions import MatterClientException
from matter_server.client.models import device_types
from matter_server.common.errors import MatterError
from matter_server.common.models import (
    CameraIceServer,
    CameraSessionEndedData,
    EventType,
    WebRTCIceCandidate,
)
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCError,
    WebRTCSendMessage,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema, MatterEntityInfo

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

# The camera commands of the Matter server API require this schema version.
CAMERA_SCHEMA_VERSION = 14

STREAM_USAGE_LIVE_VIEW = "LiveView"

# Image codec names as reported by the Matter server.
CONTENT_TYPES = {"JPEG": "image/jpeg", "HEIC": "image/heic"}


@dataclass
class _MatterWebRTCSession:
    """Bookkeeping for a single WebRTC session."""

    send_message: WebRTCSendMessage
    matter_session_id: int | None = None
    answered: bool = False
    pending_candidates: list[RTCIceCandidateInit] = field(default_factory=list)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter cameras from Config Entry."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.CAMERA, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterCameraEntityDescription(CameraEntityDescription, MatterEntityDescription):
    """Describe Matter camera entities."""


class MatterCamera(MatterEntity, Camera):
    """Representation of a Matter camera."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _platform_translation_key = "camera"
    entity_description: MatterCameraEntityDescription

    def __init__(
        self,
        matter_client: MatterClient,
        endpoint: MatterEndpoint,
        entity_info: MatterEntityInfo,
    ) -> None:
        """Initialize the Matter camera."""
        # Sessions keyed by the Home Assistant session id.
        self._sessions: dict[str, _MatterWebRTCSession] = {}
        # Reverse map from the Matter session id to the Home Assistant session id.
        self._matter_session_ids: dict[int, str] = {}
        # Events kept while an offer is in flight, so the session it creates can
        # catch up on those that arrived before its Matter session id was known.
        self._buffered_events: dict[int, list[dict[str, Any]]] = {}
        self._pending_offers = 0

        super().__init__(matter_client, endpoint, entity_info)
        Camera.__init__(self)

    @override
    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        node_id = self._endpoint.node.node_id
        self.async_on_remove(
            self.matter_client.subscribe_events(
                callback=self._on_webrtc_callback,
                event_filter=EventType.WEBRTC_CALLBACK,
                node_filter=node_id,
            )
        )
        self.async_on_remove(
            self.matter_client.subscribe_events(
                callback=self._on_session_ended,
                event_filter=EventType.CAMERA_SESSION_ENDED,
                node_filter=node_id,
            )
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Close any open WebRTC sessions when removed."""
        await super().async_will_remove_from_hass()
        for session_id in list(self._sessions):
            self.close_webrtc_session(session_id)

    @callback
    @override
    def _update_from_device(self) -> None:
        """Update from device."""
        soft_privacy = self.get_matter_attribute_value(
            CameraAvStreamManagement.Attributes.SoftLivestreamPrivacyModeEnabled
        )
        hard_privacy = self.get_matter_attribute_value(
            CameraAvStreamManagement.Attributes.HardPrivacyModeOn
        )
        self._attr_is_on = not (soft_privacy or hard_privacy)

        current_sessions = self.get_matter_attribute_value(
            WebRtcTransportProvider.Attributes.CurrentSessions
        )
        self._attr_is_streaming = bool(current_sessions)

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle a WebRTC offer from the frontend."""
        session = _MatterWebRTCSession(send_message=send_message)
        self._sessions[session_id] = session
        config = self.async_get_webrtc_client_configuration()
        ice_servers: list[CameraIceServer] = []
        for server in config.configuration.ice_servers:
            ice_server: CameraIceServer = {"urls": server.urls}
            if server.username is not None:
                ice_server["username"] = server.username
            if server.credential is not None:
                ice_server["credential"] = server.credential
            ice_servers.append(ice_server)

        self._pending_offers += 1
        try:
            result = await self.matter_client.camera_start_stream(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                stream_usage=STREAM_USAGE_LIVE_VIEW,
                sdp=offer_sdp,
                ice_servers=ice_servers or None,
            )
        except (MatterError, MatterClientException) as err:
            self._sessions.pop(session_id, None)
            raise HomeAssistantError(str(err) or type(err).__name__) from err
        else:
            matter_session_id = result.webrtc_session_id
            LOGGER.debug(
                "WebRTC session %s started for %s", matter_session_id, self.entity_id
            )
            early_events = self._buffered_events.pop(matter_session_id, [])
        finally:
            self._pending_offers -= 1
            # Drop orphaned events once no offer is in flight to claim them.
            if not self._pending_offers:
                self._buffered_events.clear()

        # The frontend may have closed the session while the offer was in flight,
        # in which case the Matter session is ended here instead.
        if self._sessions.get(session_id) is not session:
            self._stop_matter_session(matter_session_id)
            return

        session.matter_session_id = matter_session_id
        # The camera may reuse the id of a session whose end was never seen.
        self._forget_matter_session(matter_session_id)
        self._matter_session_ids[matter_session_id] = session_id

        # Catch up on events and candidates that arrived while the offer was in
        # flight; candidates are skipped if a replayed "end" already closed the session.
        for data in early_events:
            self._handle_webrtc_event(data)
        if session.pending_candidates and session_id in self._sessions:
            candidates = session.pending_candidates
            session.pending_candidates = []
            await self._provide_ice_candidates(matter_session_id, candidates)

    @override
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a WebRTC candidate from the frontend."""
        if (session := self._sessions.get(session_id)) is None:
            raise HomeAssistantError(f"Unknown WebRTC session: {session_id}")
        if session.matter_session_id is None:
            session.pending_candidates.append(candidate)
            return
        await self._provide_ice_candidates(session.matter_session_id, [candidate])

    async def _provide_ice_candidates(
        self, matter_session_id: int, candidates: list[RTCIceCandidateInit]
    ) -> None:
        """Forward ICE candidates to the camera."""
        ice_candidates = [
            WebRTCIceCandidate(
                candidate=candidate.candidate,
                sdpMid=candidate.sdp_mid,
                sdpMLineIndex=candidate.sdp_m_line_index,
            )
            for candidate in candidates
        ]
        try:
            await self.matter_client.camera_provide_ice_candidates(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                webrtc_session_id=matter_session_id,
                ice_candidates=ice_candidates,
            )
        except (MatterError, MatterClientException) as err:
            raise HomeAssistantError(str(err) or type(err).__name__) from err

    @callback
    def _on_webrtc_callback(self, event: EventType, data: dict[str, Any]) -> None:
        """Handle a WEBRTC_CALLBACK event from the Matter server."""
        if data["endpoint_id"] != self._endpoint.endpoint_id:
            return

        matter_session_id = data["webrtc_session_id"]
        session_id = self._matter_session_ids.get(matter_session_id)
        event_type = data["event_type"]

        # After a restart the camera may reuse the id of a session whose end
        # was never seen. A second answer for a known id proves that, so the
        # old session is over.
        if reused := (
            event_type == "answer"
            and session_id is not None
            and self._sessions[session_id].answered
        ):
            self._forget_matter_session(matter_session_id)

        # After a restart the camera may reuse a known id for an offer in flight,
        # so events for known ids are buffered too, though those a known session
        # got before it was over are its own. Nothing follows the "end" of a
        # session, so a buffered "end" belongs to an earlier session once
        # another event arrives.
        if self._pending_offers:
            events = self._buffered_events.setdefault(matter_session_id, [])
            if (
                reused
                or (event_type == "end" and session_id is not None)
                or (
                    event_type != "end" and events and events[-1]["event_type"] == "end"
                )
            ):
                events.clear()
            events.append(data)

        if matter_session_id in self._matter_session_ids:
            self._handle_webrtc_event(data)

    @callback
    def _handle_webrtc_event(self, data: dict[str, Any]) -> None:
        """Relay a resolved WEBRTC_CALLBACK event to the frontend."""
        matter_session_id = data["webrtc_session_id"]
        # A replayed event may follow an "end" that already removed the session.
        if (session_id := self._matter_session_ids.get(matter_session_id)) is None:
            return
        session = self._sessions[session_id]

        event_type = data["event_type"]
        if event_type == "answer":
            session.answered = True
            session.send_message(WebRTCAnswer(data["data"]["sdp"]))
        elif event_type == "ice_candidates":
            for candidate in data["data"]["ice_candidates"]:
                session.send_message(
                    WebRTCCandidate(
                        RTCIceCandidateInit(
                            candidate["candidate"],
                            sdp_mid=candidate.get("sdpMid"),
                            sdp_m_line_index=candidate.get("sdpMLineIndex"),
                        )
                    )
                )
        elif event_type == "end":
            LOGGER.debug(
                "WebRTC session %s ended: %s",
                matter_session_id,
                data["data"].get("reason"),
            )
            self._forget_matter_session(matter_session_id)

    @callback
    def _forget_matter_session(self, matter_session_id: int) -> None:
        """Drop the bookkeeping of a session the camera no longer holds."""
        if (
            session_id := self._matter_session_ids.pop(matter_session_id, None)
        ) is None:
            return
        if (session := self._sessions.pop(session_id, None)) is None:
            return
        # Without an answer the frontend is still waiting for the offer to complete.
        if not session.answered:
            session.send_message(
                WebRTCError(
                    "webrtc_session_ended", "The camera ended the WebRTC session"
                )
            )

    @callback
    def _on_session_ended(self, event: EventType, data: CameraSessionEndedData) -> None:
        """Handle a session ended by another Matter server connection."""
        # Shaped like the camera's own "end" so an offer in flight can claim it.
        self._on_webrtc_callback(
            event,
            {
                "event_type": "end",
                "webrtc_session_id": data.webrtc_session_id,
                "endpoint_id": data.endpoint_id,
                "data": {"reason": None},
            },
        )

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        super().close_webrtc_session(session_id)
        if (session := self._sessions.pop(session_id, None)) is None:
            return
        if (matter_session_id := session.matter_session_id) is None:
            # The offer is still in flight; the session is stopped once it returns.
            return
        self._matter_session_ids.pop(matter_session_id, None)
        # The events the session got are its own, not an offer in flight's.
        self._buffered_events.pop(matter_session_id, None)
        self._stop_matter_session(matter_session_id)

    @callback
    def _stop_matter_session(self, matter_session_id: int) -> None:
        """End a session on the camera in the background."""

        async def _stop_stream() -> None:
            try:
                await self.matter_client.camera_stop_stream(
                    node_id=self._endpoint.node.node_id,
                    endpoint_id=self._endpoint.endpoint_id,
                    webrtc_session_id=matter_session_id,
                )
            except (MatterError, MatterClientException) as err:
                LOGGER.debug(
                    "Error stopping WebRTC session %s: %s", matter_session_id, err
                )

        self.hass.async_create_task(
            _stop_stream(), f"matter camera {self.entity_id} stop session"
        )

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a snapshot from the camera."""
        # The server's max_resolution excludes capabilities rather than scaling,
        # so sizing is left to Home Assistant.
        try:
            result = await self.matter_client.camera_snapshot(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
            )
        except (MatterError, MatterClientException) as err:
            raise HomeAssistantError(str(err) or type(err).__name__) from err
        self.content_type = CONTENT_TYPES.get(result.codec.upper(), "image/jpeg")
        return b64decode(result.data)


DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.CAMERA,
        entity_description=MatterCameraEntityDescription(
            key="MatterCamera",
            name=None,
        ),
        entity_class=MatterCamera,
        required_attributes=(
            WebRtcTransportProvider.Attributes.CurrentSessions,
            CameraAvStreamManagement.Attributes.FeatureMap,
        ),
        optional_attributes=(
            CameraAvStreamManagement.Attributes.SoftLivestreamPrivacyModeEnabled,
            CameraAvStreamManagement.Attributes.HardPrivacyModeOn,
        ),
        device_type=(device_types.Camera,),
        server_schema_min=CAMERA_SCHEMA_VERSION,
    ),
]
