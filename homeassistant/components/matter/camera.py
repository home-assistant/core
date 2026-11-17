"""Matter camera platform."""

from base64 import b64decode
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from chip.clusters.Objects import CameraAvStreamManagement, WebRtcTransportProvider
from matter_server.client.exceptions import MatterClientException
from matter_server.client.models import device_types
from matter_server.common.errors import MatterError
from matter_server.common.models import (
    CameraIceServer,
    CameraResolutionTarget,
    CameraSessionEndedData,
    EventType,
    WebRTCIceCandidate,
)
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import (
    Camera,
    CameraEntityCapabilities,
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

CameraFeature = CameraAvStreamManagement.Bitmaps.Feature
TwoWayTalkSupportType = CameraAvStreamManagement.Enums.TwoWayTalkSupportTypeEnum

STREAM_USAGE_LIVE_VIEW = "LiveView"
MAX_ICE_SERVERS = 10


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
        # Keyed by the Home Assistant session id, which is also the session's
        # client key on the Matter server.
        self._sessions: dict[str, WebRTCSendMessage] = {}

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

        feature_map = self.get_matter_attribute_value(
            CameraAvStreamManagement.Attributes.FeatureMap
        )
        two_way_talk = self.get_matter_attribute_value(
            CameraAvStreamManagement.Attributes.TwoWayTalkSupport
        )
        self._attr_camera_entity_capabilities = CameraEntityCapabilities(
            two_way_audio=bool(feature_map & CameraFeature.kSpeaker)
            and two_way_talk
            in (TwoWayTalkSupportType.kHalfDuplex, TwoWayTalkSupportType.kFullDuplex)
        )

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle a WebRTC offer from the frontend."""
        self._sessions[session_id] = send_message
        config = self.async_get_webrtc_client_configuration()
        ice_servers: list[CameraIceServer] = []
        for server in config.configuration.ice_servers[:MAX_ICE_SERVERS]:
            ice_server: CameraIceServer = {"urls": server.urls}
            # The camera refuses empty credentials, which browsers ignore.
            if server.username:
                ice_server["username"] = server.username
            if server.credential:
                ice_server["credential"] = server.credential
            ice_servers.append(ice_server)

        try:
            result = await self.matter_client.camera_start_stream(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                stream_usage=STREAM_USAGE_LIVE_VIEW,
                sdp=offer_sdp,
                ice_servers=ice_servers or None,
                client_session_key=session_id,
                # The frontend only offers to send audio when the microphone is
                # on, so the offer is forwarded unchanged instead of letting the
                # server rewrite its audio sections to receive only.
                talkback=True,
            )
        except (MatterError, MatterClientException) as err:
            # Closing the session while the offer is in flight cancels it.
            if self._sessions.pop(session_id, None) is None:
                return
            raise HomeAssistantError(str(err) or type(err).__name__) from err
        LOGGER.debug(
            "WebRTC session %s started for %s (talkback: %s)",
            result.webrtc_session_id,
            self.entity_id,
            result.talkback,
        )

    @override
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a WebRTC candidate from the frontend."""
        if session_id not in self._sessions:
            raise HomeAssistantError(f"Unknown WebRTC session: {session_id}")
        # The server holds candidates until the camera has the offer.
        try:
            await self.matter_client.camera_provide_ice_candidates(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                webrtc_session_id=None,
                ice_candidates=[
                    WebRTCIceCandidate(
                        candidate=candidate.candidate,
                        sdpMid=candidate.sdp_mid,
                        sdpMLineIndex=candidate.sdp_m_line_index,
                    )
                ],
                client_session_key=session_id,
            )
        except (MatterError, MatterClientException) as err:
            raise HomeAssistantError(str(err) or type(err).__name__) from err

    @callback
    def _on_webrtc_callback(self, event: EventType, data: dict[str, Any]) -> None:
        """Relay the camera's signalling to the frontend."""
        if (key := data.get("client_session_key")) is None or (
            send_message := self._sessions.get(key)
        ) is None:
            return

        event_type = data["event_type"]
        if event_type == "answer":
            send_message(WebRTCAnswer(data["data"]["sdp"]))
        elif event_type == "ice_candidates":
            for candidate in data["data"]["ice_candidates"]:
                send_message(
                    WebRTCCandidate(
                        RTCIceCandidateInit(
                            candidate["candidate"],
                            sdp_mid=candidate.get("sdpMid"),
                            sdp_m_line_index=candidate.get("sdpMLineIndex"),
                        )
                    )
                )

    @callback
    def _on_session_ended(self, event: EventType, data: CameraSessionEndedData) -> None:
        """Handle a session that ended without Home Assistant stopping it."""
        if (
            data.client_session_key is None
            or (send_message := self._sessions.pop(data.client_session_key, None))
            is None
        ):
            return
        LOGGER.debug("WebRTC session %s ended: %s", data.webrtc_session_id, data.cause)
        send_message(
            WebRTCError("webrtc_session_ended", "The camera ended the WebRTC session")
        )

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        super().close_webrtc_session(session_id)
        if self._sessions.pop(session_id, None) is None:
            return

        async def _stop_stream() -> None:
            try:
                await self.matter_client.camera_stop_stream(
                    node_id=self._endpoint.node.node_id,
                    endpoint_id=self._endpoint.endpoint_id,
                    client_session_key=session_id,
                )
            except (MatterError, MatterClientException) as err:
                LOGGER.debug("Error stopping WebRTC session %s: %s", session_id, err)

        self.hass.async_create_task(
            _stop_stream(), f"matter camera {self.entity_id} stop session"
        )

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a snapshot from the camera."""
        resolution: CameraResolutionTarget = {}
        if width is not None:
            resolution["width"] = width
        if height is not None:
            resolution["height"] = height
        try:
            result = await self.matter_client.camera_snapshot(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                # Most browsers cannot show HEIC, and Home Assistant only scales JPEG.
                codec="JPEG",
                resolution=resolution or None,
            )
        except (MatterError, MatterClientException) as err:
            raise HomeAssistantError(str(err) or type(err).__name__) from err
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
            CameraAvStreamManagement.Attributes.TwoWayTalkSupport,
        ),
        device_type=(device_types.Camera,),
        server_schema_min=CAMERA_SCHEMA_VERSION,
    ),
]
