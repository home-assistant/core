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

_STREAM_USAGE = clusters.Globals.Enums.StreamUsageEnum.kLiveView
# Minimum resolution requested for the video stream; the camera negotiates the
# actual encoding within this and the (sensor-derived, when available) max bound.
_MIN_RESOLUTION = clusters.CameraAvStreamManagement.Structs.VideoResolutionStruct(
    width=640, height=480
)
_FALLBACK_MAX_RESOLUTION = (
    clusters.CameraAvStreamManagement.Structs.VideoResolutionStruct(
        width=1920, height=1080
    )
)
_FALLBACK_MAX_FRAME_RATE = 120
_MIN_FRAME_RATE = 30
_PREFERRED_AUDIO_CODEC = clusters.CameraAvStreamManagement.Enums.AudioCodecEnum.kOpus
_PREFERRED_SAMPLE_RATE = 48000
_PREFERRED_BIT_DEPTH = 24


def _preferred_or_first[T](preferred: T, supported: list[T]) -> T:
    """Return preferred if the device supports it, else the first supported value."""
    if not supported:
        return preferred
    return preferred if preferred in supported else supported[0]


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
        # Video/audio stream allocated for live view, and whether we allocated
        # it ourselves (and so must free it once no session uses it anymore),
        # as opposed to reusing a stream already allocated by another party.
        self._video_stream_id: int | None = None
        self._video_stream_owned = False
        self._audio_stream_id: int | None = None
        self._audio_stream_owned = False
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

    def _stream_id_from_response(self, response: dict[str, Any], key: str) -> int:
        """Extract e.g. "videoStreamID" from a stream Allocate response.

        Works around a matterjs-server bug where the response uses matter.js's
        own field-name casing (e.g. "videoStreamId") instead of the chip-clusters
        convention this integration expects. Remove once fixed upstream:
        https://github.com/matter-js/matterjs-server/issues/927
        """
        if key in response:
            return int(response[key])
        return int(response[key[:-2] + "Id"])

    async def _async_ensure_video_stream(self) -> int:
        """Return a video stream ID for live view, reusing or allocating one."""
        if self._video_stream_id is not None:
            return self._video_stream_id
        allocated_streams = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.AllocatedVideoStreams
        )
        for stream in allocated_streams or []:
            if stream.streamUsage == _STREAM_USAGE:
                self._video_stream_id = stream.videoStreamID
                self._video_stream_owned = False
                return self._video_stream_id
        feature_map = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.FeatureMap
        )
        # Prefer the camera's own reported sensor bounds (native resolution and
        # frame rate) over the fallback constants when available.
        video_sensor_params = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.VideoSensorParams
        )
        if video_sensor_params is not None:
            max_resolution = (
                clusters.CameraAvStreamManagement.Structs.VideoResolutionStruct(
                    width=video_sensor_params.sensorWidth,
                    height=video_sensor_params.sensorHeight,
                )
            )
            max_frame_rate = video_sensor_params.maxFps
        else:
            max_resolution = _FALLBACK_MAX_RESOLUTION
            max_frame_rate = _FALLBACK_MAX_FRAME_RATE
        # MaxEncodedPixelRate reflects what the encoder can actually sustain at a
        # given resolution, which can be lower than the sensor's absolute max fps.
        max_encoded_pixel_rate = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.MaxEncodedPixelRate
        )
        if max_encoded_pixel_rate is not None:
            pixel_rate_fps = max_encoded_pixel_rate // (
                max_resolution.width * max_resolution.height
            )
            max_frame_rate = min(max_frame_rate, pixel_rate_fps)
        allocate_kwargs: dict[str, Any] = {
            "streamUsage": _STREAM_USAGE,
            "videoCodec": clusters.CameraAvStreamManagement.Enums.VideoCodecEnum.kH264,
            "minFrameRate": min(_MIN_FRAME_RATE, max_frame_rate),
            "maxFrameRate": max_frame_rate,
            "minResolution": _MIN_RESOLUTION,
            "maxResolution": max_resolution,
            "minBitRate": 10000,
            "maxBitRate": 10000,
            "keyFrameInterval": 4000,
        }
        # watermarkEnabled/osdEnabled are mandatory when the corresponding feature
        # bit is advertised (Matter spec 11.2.1.2.1), optional otherwise.
        avsm_feature = clusters.CameraAvStreamManagement.Bitmaps.Feature
        if feature_map & avsm_feature.kWatermark:
            allocate_kwargs["watermarkEnabled"] = False
        if feature_map & avsm_feature.kOnScreenDisplay:
            allocate_kwargs["osdEnabled"] = False
        response = await self.send_device_command(
            clusters.CameraAvStreamManagement.Commands.VideoStreamAllocate(
                **allocate_kwargs
            )
        )
        self._video_stream_id = self._stream_id_from_response(response, "videoStreamID")
        self._video_stream_owned = True
        return self._video_stream_id

    async def _async_ensure_audio_stream(self) -> int | None:
        """Return an audio stream ID for live view, reusing or allocating one.

        Audio is best-effort: not all Matter cameras expose a microphone.
        """
        if self._audio_stream_id is not None:
            return self._audio_stream_id
        allocated_streams = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.AllocatedAudioStreams
        )
        for stream in allocated_streams or []:
            if stream.streamUsage == _STREAM_USAGE:
                self._audio_stream_id = stream.audioStreamID
                self._audio_stream_owned = False
                return self._audio_stream_id
        # Prefer the camera's own reported codec/sample-rate/bit-depth support
        # over the preferred defaults, to avoid requesting a combination the
        # microphone doesn't support.
        mic_capabilities = self.get_matter_attribute_value(
            clusters.CameraAvStreamManagement.Attributes.MicrophoneCapabilities
        )
        if mic_capabilities is not None:
            audio_codec = _preferred_or_first(
                _PREFERRED_AUDIO_CODEC, mic_capabilities.supportedCodecs
            )
            sample_rate = _preferred_or_first(
                _PREFERRED_SAMPLE_RATE, mic_capabilities.supportedSampleRates
            )
            bit_depth = _preferred_or_first(
                _PREFERRED_BIT_DEPTH, mic_capabilities.supportedBitDepths
            )
        else:
            audio_codec = _PREFERRED_AUDIO_CODEC
            sample_rate = _PREFERRED_SAMPLE_RATE
            bit_depth = _PREFERRED_BIT_DEPTH
        try:
            response = await self.send_device_command(
                clusters.CameraAvStreamManagement.Commands.AudioStreamAllocate(
                    streamUsage=_STREAM_USAGE,
                    audioCodec=audio_codec,
                    channelCount=1,
                    sampleRate=sample_rate,
                    bitRate=20000,
                    bitDepth=bit_depth,
                )
            )
        except HomeAssistantError:
            LOGGER.debug(
                "AudioStreamAllocate failed for %s, continuing video-only",
                self.entity_id,
                exc_info=True,
            )
            return None
        self._audio_stream_id = self._stream_id_from_response(response, "audioStreamID")
        self._audio_stream_owned = True
        return self._audio_stream_id

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
        try:
            # A null videoStreamID/audioStreamID in ProvideOffer only asks the
            # camera to auto-select among streams it has *already* allocated for
            # this StreamUsage (Matter spec 11.2.1.2.1); with none allocated yet,
            # the camera has nothing to select and fails the whole offer with
            # InvalidInState. Ensure a matching stream exists (reusing one if
            # already allocated) before offering.
            video_stream_id = await self._async_ensure_video_stream()
            audio_stream_id = await self._async_ensure_audio_stream()
        except HomeAssistantError:
            self._sessions.pop(session_id, None)
            raise
        self._pending_offers += 1
        payload: dict[str, Any] = {
            # null session id requests a new session
            "webRtcSessionID": None,
            "sdp": offer_sdp,
            "streamUsage": clusters.Globals.Enums.StreamUsageEnum.kLiveView,
            "videoStreamID": video_stream_id,
            "iceServers": ice_servers,
        }
        # Omit rather than send a null audioStreamID: a null id asks the camera
        # to auto-select an already-allocated audio stream (Matter spec
        # 11.2.1.2.1), which fails the whole offer with InvalidInState if none
        # exists at all, instead of the video-only fallback intended when audio
        # allocation failed or isn't supported.
        if audio_stream_id is not None:
            payload["audioStreamID"] = audio_stream_id
        try:
            response = await self.matter_client.send_webrtc_provider_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command_name="ProvideOffer",
                payload=payload,
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
            self._free_owned_streams_if_unused()

    @callback
    def _free_owned_streams_if_unused(self) -> None:
        """Free video/audio streams we allocated once no session uses them.

        Runs synchronously (rather than in the async deallocate task below) so
        a fast stop+restart can't reuse a stream ID before the device has
        processed the deallocate, which it would then reject as no longer
        allocated.
        """
        if self._sessions:
            return
        owned_video_stream_id = (
            self._video_stream_id if self._video_stream_owned else None
        )
        owned_audio_stream_id = (
            self._audio_stream_id if self._audio_stream_owned else None
        )
        self._video_stream_id = None
        self._video_stream_owned = False
        self._audio_stream_id = None
        self._audio_stream_owned = False
        if owned_video_stream_id is None and owned_audio_stream_id is None:
            return

        async def _deallocate() -> None:
            if owned_video_stream_id is not None:
                try:
                    await self.send_device_command(
                        clusters.CameraAvStreamManagement.Commands.VideoStreamDeallocate(
                            videoStreamID=owned_video_stream_id
                        )
                    )
                except HomeAssistantError:
                    LOGGER.debug(
                        "VideoStreamDeallocate failed for %s",
                        self.entity_id,
                        exc_info=True,
                    )
            if owned_audio_stream_id is not None:
                try:
                    await self.send_device_command(
                        clusters.CameraAvStreamManagement.Commands.AudioStreamDeallocate(
                            audioStreamID=owned_audio_stream_id
                        )
                    )
                except HomeAssistantError:
                    LOGGER.debug(
                        "AudioStreamDeallocate failed for %s",
                        self.entity_id,
                        exc_info=True,
                    )

        self.hass.async_create_task(
            _deallocate(), f"matter camera {self.entity_id} deallocate streams"
        )

    @callback
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
        super().close_webrtc_session(session_id)
        if (session := self._sessions.pop(session_id, None)) is None:
            return
        if (matter_session_id := session.matter_session_id) is not None:
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
        self._free_owned_streams_if_unused()

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
            clusters.CameraAvStreamManagement.Attributes.AllocatedVideoStreams,
            clusters.CameraAvStreamManagement.Attributes.AllocatedAudioStreams,
        ),
        allow_none_value=True,
    ),
]
