"""Matter camera platform."""

import base64
from dataclasses import dataclass, field
from typing import Any, override

from chip.clusters import Objects as clusters
from matter_server.common.errors import MatterError
from matter_server.common.models import (
    CameraIceServer,
    CameraSessionEndedData,
    CameraStreamEvictedData,
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

STREAM_USAGE_LIVE_VIEW = "LiveView"


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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Matter camera."""
        # Sessions keyed by the Home Assistant session id.
        self._sessions: dict[str, MatterWebRTCSession] = {}
        # Reverse map from the Matter session id to the Home Assistant session id.
        self._matter_session_ids: dict[int, str] = {}
        super().__init__(*args, **kwargs)
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
                callback=self._on_camera_session_ended,
                event_filter=EventType.CAMERA_SESSION_ENDED,
                node_filter=node_id,
            )
        )
        self.async_on_remove(
            self.matter_client.subscribe_events(
                callback=self._on_camera_stream_evicted,
                event_filter=EventType.CAMERA_STREAM_EVICTED,
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
        ice_servers: list[CameraIceServer] = []
        for server in config.configuration.ice_servers:
            ice_server: CameraIceServer = {"urls": server.urls}
            if server.username is not None:
                ice_server["username"] = server.username
            if server.credential is not None:
                ice_server["credential"] = server.credential
            ice_servers.append(ice_server)
        try:
            result = await self.matter_client.camera_start_stream(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                stream_usage=STREAM_USAGE_LIVE_VIEW,
                sdp=offer_sdp,
                ice_servers=ice_servers,
            )
        except MatterError as err:
            self._sessions.pop(session_id, None)
            raise HomeAssistantError(str(err) or type(err).__name__) from err

        session.matter_session_id = result.webrtc_session_id
        self._matter_session_ids[result.webrtc_session_id] = session_id

        # Flush candidates the frontend sent while the offer was in flight.
        if session.pending_candidates:
            candidates = session.pending_candidates
            session.pending_candidates = []
            await self._provide_ice_candidates(result.webrtc_session_id, candidates)

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
        except MatterError as err:
            raise HomeAssistantError(str(err) or type(err).__name__) from err

    @callback
    def _on_webrtc_callback(self, event: EventType, data: dict[str, Any]) -> None:
        """Relay a WEBRTC_CALLBACK event from the Matter server to the frontend."""
        if data["endpoint_id"] != self._endpoint.endpoint_id:
            return
        matter_session_id = data["webrtc_session_id"]
        if matter_session_id not in self._matter_session_ids:
            return
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
    def _on_camera_session_ended(
        self, event: EventType, data: CameraSessionEndedData
    ) -> None:
        """Handle a session another connection ended for this camera."""
        if data.endpoint_id != self._endpoint.endpoint_id:
            return
        session_id = self._matter_session_ids.pop(data.webrtc_session_id, None)
        if session_id is not None:
            self._sessions.pop(session_id, None)

    @callback
    def _on_camera_stream_evicted(
        self, event: EventType, data: CameraStreamEvictedData
    ) -> None:
        """Log a stream the server deallocated to make room for another request."""
        if data.endpoint_id != self._endpoint.endpoint_id:
            return
        LOGGER.debug("Camera stream %s (%s) was evicted", data.stream_id, data.kind)

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

        async def _stop_stream() -> None:
            try:
                await self.matter_client.camera_stop_stream(
                    node_id=self._endpoint.node.node_id,
                    endpoint_id=self._endpoint.endpoint_id,
                    webrtc_session_id=matter_session_id,
                )
            except MatterError as err:
                LOGGER.debug(
                    "Error ending WebRTC session %s: %s", matter_session_id, err
                )

        self.hass.async_create_task(_stop_stream())

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        try:
            result = await self.matter_client.camera_snapshot(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
            )
        except MatterError as err:
            raise HomeAssistantError(str(err) or type(err).__name__) from err

        async def _release_stream() -> None:
            try:
                await self.matter_client.camera_release_stream(
                    node_id=self._endpoint.node.node_id,
                    endpoint_id=self._endpoint.endpoint_id,
                    kind="snapshot",
                    stream_id=result.stream_id,
                )
            except MatterError as err:
                LOGGER.debug(
                    "Error releasing snapshot stream %s: %s", result.stream_id, err
                )

        self.hass.async_create_task(_release_stream())
        return base64.b64decode(result.data)


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
