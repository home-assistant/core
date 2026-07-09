"""Matter camera platform."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, override

from chip.clusters import Objects as clusters
from chip.clusters.Objects import NullValue
from matter_server.common.errors import MatterError
from matter_server.common.models import EventType
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCSendMessage,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema

PLACEHOLDER = Path(__file__).parent / "placeholder.png"


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


@dataclass
class MatterWebRTCSession:
    """Bookkeeping for a single WebRTC session."""

    send_message: WebRTCSendMessage
    matter_session_id: int | None = None
    pending_candidates: list[RTCIceCandidateInit] = field(default_factory=list)


class MatterCamera(MatterEntity, Camera):
    """Representation of a Matter camera."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _platform_translation_key = "camera"
    entity_description: MatterCameraEntityDescription
    _placeholder_image: ClassVar[bytes | None] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Matter camera."""
        # Sessions keyed by the Home Assistant session id.
        self._sessions: dict[str, MatterWebRTCSession] = {}
        # Reverse map from the Matter session id to the Home Assistant session id.
        self._matter_session_ids: dict[int, str] = {}
        # WEBRTC_CALLBACK events whose Matter session id is not yet known, kept
        # only while an offer is in flight to bound growth.
        self._buffered_events: list[dict[str, Any]] = []
        self._pending_offers = 0
        super().__init__(*args, **kwargs)
        Camera.__init__(self)

    @override
    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await super().async_added_to_hass()
        # WEBRTC_CALLBACK events are forwarded without a node id, so they cannot
        # be node-filtered; subscribe to all and filter inside the callback.
        self._unsubscribes.append(
            self.matter_client.subscribe_events(
                callback=self._on_webrtc_callback,
                event_filter=EventType.WEBRTC_CALLBACK,
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
            clusters.CameraAvStreamManagement.Attributes.SoftLivestreamPrivacyModeEnabled
        )
        hard_privacy = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.HardPrivacyModeOn
        )
        self._attr_is_on = not (soft_privacy or hard_privacy)
        current_sessions = self.get_matter_attribute_value(
            clusters.WebRtcTransportProvider.Attributes.CurrentSessions
        )
        self._attr_is_streaming = bool(current_sessions)

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle a WebRTC offer from the frontend."""
        session = MatterWebRTCSession(send_message=send_message)
        self._sessions[session_id] = session
        config = self.async_get_webrtc_client_configuration()
        ice_servers = [
            clusters.WebRtcTransportDefinitions.Structs.ICEServerStruct(
                urLs=[server.urls] if isinstance(server.urls, str) else server.urls,
                username=server.username,
                credential=server.credential,
            )
            for server in config.configuration.ice_servers
        ]
        self._pending_offers += 1
        try:
            response = await self.matter_client.send_webrtc_provider_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command_name="ProvideOffer",
                payload={
                    # null session id requests a new session
                    "webRtcSessionID": None,
                    "sdp": offer_sdp,
                    "streamUsage": clusters.Globals.Enums.StreamUsageEnum.kLiveView,
                    # null stream ids request automatic stream selection by the camera
                    "videoStreamID": None,
                    "audioStreamID": None,
                    "iceServers": ice_servers,
                },
            )
        except MatterError as err:
            self._sessions.pop(session_id, None)
            raise HomeAssistantError(str(err) or type(err).__name__) from err
        finally:
            self._pending_offers -= 1

        matter_session_id = response["webRtcSessionId"]
        session.matter_session_id = matter_session_id
        self._matter_session_ids[matter_session_id] = session_id

        # Replay device events that arrived before the session id was known.
        for data in [
            event
            for event in self._buffered_events
            if event["webrtc_session_id"] == matter_session_id
        ]:
            self._buffered_events.remove(data)
            self._handle_webrtc_event(data)
        # Drop orphaned events once no offers remain in flight.
        if not self._pending_offers:
            self._buffered_events.clear()

        # Flush candidates the frontend sent while the offer was in flight.
        if session.pending_candidates:
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
            clusters.WebRtcTransportDefinitions.Structs.ICECandidateStruct(
                candidate=candidate.candidate,
                sdpMid=candidate.sdp_mid
                if candidate.sdp_mid is not None
                else NullValue,
                sdpmLineIndex=candidate.sdp_m_line_index
                if candidate.sdp_m_line_index is not None
                else NullValue,
            )
            for candidate in candidates
        ]
        await self.send_device_command(
            clusters.WebRtcTransportProvider.Commands.ProvideIceCandidates(
                webRtcSessionID=matter_session_id,
                iceCandidates=ice_candidates,
            )
        )

    @callback
    def _on_webrtc_callback(self, event: EventType, data: dict[str, Any]) -> None:
        """Handle a WEBRTC_CALLBACK event from the Matter server."""
        if (
            data["node_id"] != self._endpoint.node.node_id
            or data["endpoint_id"] != self._endpoint.endpoint_id
        ):
            return
        if data["webrtc_session_id"] not in self._matter_session_ids:
            if self._pending_offers:
                self._buffered_events.append(data)
            return
        self._handle_webrtc_event(data)

    @callback
    def _handle_webrtc_event(self, data: dict[str, Any]) -> None:
        """Relay a resolved WEBRTC_CALLBACK event to the frontend."""
        matter_session_id = data["webrtc_session_id"]
        session_id = self._matter_session_ids[matter_session_id]
        session = self._sessions[session_id]
        event_type = data["event_type"]
        if event_type == "answer":
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
            self._sessions.pop(session_id, None)
            self._matter_session_ids.pop(matter_session_id, None)

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        super().close_webrtc_session(session_id)
        if (session := self._sessions.pop(session_id, None)) is None:
            return
        if (matter_session_id := session.matter_session_id) is None:
            return
        self._matter_session_ids.pop(matter_session_id, None)

        async def _end_session() -> None:
            try:
                await self.matter_client.send_device_command(
                    node_id=self._endpoint.node.node_id,
                    endpoint_id=self._endpoint.endpoint_id,
                    command=clusters.WebRtcTransportProvider.Commands.EndSession(
                        webRtcSessionID=matter_session_id,
                        reason=clusters.WebRtcTransportDefinitions.Enums.WebRTCEndReasonEnum.kUserHangup,
                    ),
                )
            except MatterError as err:
                LOGGER.debug(
                    "Error ending WebRTC session %s: %s", matter_session_id, err
                )

        self.hass.async_create_task(_end_session())

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a placeholder image.

        Matter WebRTC cameras do not currently support snapshots.
        """
        if MatterCamera._placeholder_image is None:
            MatterCamera._placeholder_image = await self.hass.async_add_executor_job(
                PLACEHOLDER.read_bytes
            )
        return MatterCamera._placeholder_image


DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.CAMERA,
        entity_description=MatterCameraEntityDescription(
            key="MatterCamera",
            name=None,
        ),
        entity_class=MatterCamera,
        required_attributes=(
            clusters.WebRtcTransportProvider.Attributes.CurrentSessions,
        ),
        optional_attributes=(
            clusters.CameraAvStreamManagement.Attributes.SoftLivestreamPrivacyModeEnabled,
            clusters.CameraAvStreamManagement.Attributes.HardPrivacyModeOn,
        ),
        allow_none_value=True,
    ),
]
