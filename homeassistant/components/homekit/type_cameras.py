"""Class to hold all camera accessories."""

import asyncio
from datetime import timedelta
import logging
import shlex
from typing import TYPE_CHECKING, Any, override

from haffmpeg.core import FFMPEG_STDERR, HAFFmpeg
from homekit_audio_proxy import AudioProxy
from pyhap.camera import (
    VIDEO_CODEC_PARAM_LEVEL_TYPES,
    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES,
    Camera as PyhapCamera,
)
from pyhap.const import CATEGORY_CAMERA
from pyhap.util import callback as pyhap_callback

from homeassistant.components import camera
from homeassistant.components.camera.const import PREF_ORIENTATION  # pylint: disable=home-assistant-component-root-import
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.stream import Orientation
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HassJobType,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util.async_ import create_eager_task

from .accessories import TYPES, HomeDriver
from .const import (
    CHAR_MOTION_DETECTED,
    CONF_AUDIO_CODEC,
    CONF_AUDIO_MAP,
    CONF_AUDIO_PACKET_SIZE,
    CONF_LINKED_MOTION_SENSOR,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
    CONF_SECURE_VIDEO,
    CONF_SECURE_VIDEO_NATIVE,
    CONF_SECURE_VIDEO_PREBUFFER,
    CONF_SECURE_VIDEO_QUALITY,
    CONF_SECURE_VIDEO_RECEIVE_TIMESTAMPS,
    CONF_STREAM_ADDRESS,
    CONF_STREAM_COUNT,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    CONF_VIDEO_MAP,
    CONF_VIDEO_PACKET_SIZE,
    CONF_VIDEO_PROFILE_NAMES,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_MAP,
    DEFAULT_AUDIO_PACKET_SIZE,
    DEFAULT_MAX_FPS,
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_SECURE_VIDEO_PREBUFFER,
    DEFAULT_SECURE_VIDEO_RECEIVE_TIMESTAMPS,
    DEFAULT_STREAM_COUNT,
    DEFAULT_SUPPORT_AUDIO,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_MAP,
    DEFAULT_VIDEO_PACKET_SIZE,
    DEFAULT_VIDEO_PROFILE_NAMES,
    SECURE_VIDEO_QUALITY_COMPATIBLE,
    SERV_MOTION_SENSOR,
)
from .doorbell import HomeDoorbellAccessory
from .hksv_controller import HKSVController
from .hksv_hardware import HARDWARE_ENCODER_PROBE as _HARDWARE_PROBE, HardwareEncoder
from .hksv_media import orientation_video_filter
from .hksv_rtp import NativeVideoSender
from .hksv_stream import MediaObservation, SharedCameraStream
from .util import pid_is_alive, state_changed_event_is_same_state

_LOGGER = logging.getLogger(__name__)


VIDEO_OUTPUT = (
    "-map {v_map} -an "
    "-c:v {v_codec} "
    "{v_options}"
    "{v_rate_control}"
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&"
    "localrtpport={v_port}&pkt_size={v_pkt_size}"
)

AUDIO_OUTPUT = (
    "-map {a_map} -vn "
    "-c:a {a_encoder} "
    "{a_application}"
    "-ac 1 -ar {a_sample_rate}k "
    "-b:a {a_max_bitrate}k -bufsize {a_bufsize}k "
    "{a_frame_duration}"
    "-payload_type 110 "
    "-ssrc {a_ssrc} -f rtp "
    "rtp://127.0.0.1:{a_proxy_port}?pkt_size={a_pkt_size}"
)

SLOW_RESOLUTIONS = [
    (320, 180, 15),
    (320, 240, 15),
]

RESOLUTIONS = [
    (320, 180),
    (320, 240),
    (480, 270),
    (480, 360),
    (640, 360),
    (640, 480),
    (1024, 576),
    (1024, 768),
    (1280, 720),
    (1280, 960),
    (1920, 1080),
    (1600, 1200),
]

FFMPEG_WATCH_INTERVAL = timedelta(seconds=5)
SNAPSHOT_TIMEOUT = 15
FFMPEG_LOGGER = "ffmpeg_logger"
FFMPEG_WATCHER = "ffmpeg_watcher"
FFMPEG_PID = "ffmpeg_pid"
FFMPEG_DIAGNOSTICS = "ffmpeg_diagnostics"
FFMPEG_LIVE_HARDWARE = "ffmpeg_live_hardware"
FFMPEG_INPUT_TASK = "ffmpeg_input_task"
FFMPEG_SHARED = "ffmpeg_shared"
FFMPEG_AUDIO_TASK = "ffmpeg_audio_task"
NATIVE_VIDEO_TASK = "native_video_task"
AUDIO_PROXY = "audio_proxy"
SESSION_ID = "session_id"

CONFIG_DEFAULTS = {
    CONF_SUPPORT_AUDIO: DEFAULT_SUPPORT_AUDIO,
    CONF_MAX_WIDTH: DEFAULT_MAX_WIDTH,
    CONF_MAX_HEIGHT: DEFAULT_MAX_HEIGHT,
    CONF_MAX_FPS: DEFAULT_MAX_FPS,
    CONF_AUDIO_CODEC: DEFAULT_AUDIO_CODEC,
    CONF_AUDIO_MAP: DEFAULT_AUDIO_MAP,
    CONF_VIDEO_MAP: DEFAULT_VIDEO_MAP,
    CONF_VIDEO_CODEC: DEFAULT_VIDEO_CODEC,
    CONF_VIDEO_PROFILE_NAMES: DEFAULT_VIDEO_PROFILE_NAMES,
    CONF_AUDIO_PACKET_SIZE: DEFAULT_AUDIO_PACKET_SIZE,
    CONF_VIDEO_PACKET_SIZE: DEFAULT_VIDEO_PACKET_SIZE,
    CONF_STREAM_COUNT: DEFAULT_STREAM_COUNT,
}


def live_video_compatible(
    observed: MediaObservation,
    profile: int,
    level: int,
    width: int,
    height: int,
    fps: int,
    max_bitrate: int,
) -> bool:
    """Check observed source video against a HomeKit live selection."""
    profiles = (66, 77, 100)
    levels = (31, 32, 40)
    if profile not in range(len(profiles)) or level not in range(len(levels)):
        return False
    try:
        source_profile = profiles.index(observed.h264_profile_idc)
    except ValueError:
        return False
    return (
        observed.video_codec == "h264"
        and source_profile <= profile
        and (source_profile != 0 or observed.h264_compatibility & 0x40 != 0)
        and observed.h264_level_idc <= levels[level]
        and observed.width == width
        and observed.height == height
        and 0 < observed.peak_fps <= fps
        and 0 < observed.peak_video_bitrate <= max_bitrate * 1000
        and observed.observation_seconds >= 2
    )


@TYPES.register("Camera")
# False-positive on pylint, not a CameraEntity
# pylint: disable-next=home-assistant-enforce-class-module
class Camera(HomeDoorbellAccessory, PyhapCamera):  # type: ignore[misc]
    """Generate a Camera accessory."""

    def __init__(
        self,
        hass: HomeAssistant,
        driver: HomeDriver,
        name: str,
        entity_id: str,
        aid: int,
        config: dict[str, Any],
    ) -> None:
        """Initialize a Camera accessory object."""
        self._ffmpeg = get_ffmpeg_manager(hass)
        for config_key, conf in CONFIG_DEFAULTS.items():
            if config_key not in config:
                config[config_key] = conf

        max_fps = config[CONF_MAX_FPS]
        max_width = config[CONF_MAX_WIDTH]
        max_height = config[CONF_MAX_HEIGHT]
        resolutions = [
            (w, h, fps)
            for w, h, fps in SLOW_RESOLUTIONS
            if w <= max_width and h <= max_height and fps < max_fps
        ] + [
            (w, h, max_fps)
            for w, h in RESOLUTIONS
            if w <= max_width and h <= max_height
        ]

        video_options = {
            "codec": {
                "profiles": [
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["BASELINE"],
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["MAIN"],
                    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["HIGH"],
                ],
                "levels": [
                    VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE3_1"],
                    VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE3_2"],
                    VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE4_0"],
                ],
            },
            "resolutions": resolutions,
        }
        audio_options = {
            "codecs": [
                {"type": "OPUS", "samplerate": 24},
                {"type": "OPUS", "samplerate": 16},
            ]
        }

        stream_address = config.get(CONF_STREAM_ADDRESS, driver.state.address)

        options = {
            "video": video_options,
            "audio": audio_options,
            "address": stream_address,
            "srtp": True,
            "stream_count": config[CONF_STREAM_COUNT],
        }

        super().__init__(
            hass,
            driver,
            name,
            entity_id,
            aid,
            config,
            category=CATEGORY_CAMERA,
            options=options,
        )

        self._hksv: HKSVController | None = None
        self._hksv_start_task: asyncio.Task[None] | None = None
        self._camera_stop_task: asyncio.Task[None] | None = None
        self._camera_stream_stop_tasks: list[asyncio.Task[None]] = []
        self._camera_stopping = False
        self._hksv_stream_chars: list[Any] = []
        self._hksv_motion_active: Any = None
        self._char_motion_detected = None
        self.linked_motion_sensor: str | None = self.config.get(
            CONF_LINKED_MOTION_SENSOR
        )
        self.motion_is_event = False
        state = None
        if linked_motion_sensor := self.linked_motion_sensor:
            self.motion_is_event = linked_motion_sensor.startswith("event.")
            state = self.hass.states.get(linked_motion_sensor)
            if state is not None or self.config.get(CONF_SECURE_VIDEO, False):
                serv_motion = self.add_preload_service(SERV_MOTION_SENSOR)
                self._char_motion_detected = serv_motion.configure_char(
                    CHAR_MOTION_DETECTED, value=False
                )
                if state is not None:
                    self._async_update_motion_state(None, state)

        if self.config.get(CONF_SECURE_VIDEO, False):
            if self.config.get(CONF_STREAM_SOURCE):
                _LOGGER.error(
                    "%s: Secure Video is unavailable with an explicit stream source; "
                    "the live camera remains available",
                    self.entity_id,
                )
            elif not self._char_motion_detected:
                _LOGGER.error(
                    "%s: Secure Video requires a linked motion sensor", self.entity_id
                )
            elif max_width < 1920 or max_height < 1080 or max_fps < 30:
                _LOGGER.error(
                    "%s: Secure Video requires 1920x1080 at 30 fps", self.entity_id
                )
            else:
                try:
                    controller = HKSVController(
                        self.driver,
                        self._async_get_hksv_source,
                        self._ffmpeg.binary,
                        Store(
                            self.hass,
                            1,
                            f"homekit.hksv.{self.driver.entry_id}.{self.entity_id}",
                        ),
                        self._hksv_stop_live,
                        self._hksv_sync_characteristics,
                        self._hksv_stop_live,
                        camera_entity_id=self.entity_id,
                        preserve_source=self.config.get(CONF_SECURE_VIDEO_NATIVE, True),
                        quality=self.config.get(
                            CONF_SECURE_VIDEO_QUALITY, SECURE_VIDEO_QUALITY_COMPATIBLE
                        ),
                        on_capabilities_changed=self._hksv_capabilities_changed,
                        prebuffer_seconds=self.config.get(
                            CONF_SECURE_VIDEO_PREBUFFER, DEFAULT_SECURE_VIDEO_PREBUFFER
                        ),
                    )
                except Exception:
                    _LOGGER.exception(
                        "%s: Could not initialize Secure Video", self.entity_id
                    )
                else:
                    services = controller.services
                    self.add_service(
                        services.recording, services.operating, services.transport
                    )
                    services.recording.add_linked_service(services.transport)
                    services.recording.add_linked_service(serv_motion)
                    self._hksv = controller
                    if not self.motion_is_event and state is not None:
                        controller.motion(state.state == STATE_ON)
                    self._hksv_motion_active = self._hksv_add_characteristic(
                        serv_motion, "StatusActive", True
                    )
                    for index, management in enumerate(self._management):
                        char = management.get_characteristic("Active")
                        char.setter_callback = lambda value, index=index, char=char: (
                            self._hksv_set_stream_active(index, char, value)
                        )
                        self._hksv_stream_chars.append(char)

    def _hksv_add_characteristic(self, service: Any, name: str, value: Any) -> Any:
        """Attach a characteristic before the accessory is advertised."""
        char = self.driver.loader.get_char(name)
        service.add_characteristic(char)
        char.broker = self
        self.iid_manager.assign(char)
        char.set_value(value, should_notify=False)
        return char

    @callback
    def _hksv_sync_characteristics(self) -> None:
        """Reflect restored operating mode and per-stream settings."""
        assert self._hksv is not None
        for index, char in enumerate(self._hksv_stream_chars):
            char.set_value(int(self._hksv.stream_active(index)))
        if self._hksv_motion_active is not None:
            self._hksv_motion_active.set_value(self._hksv.camera_active)

    @callback
    def _hksv_set_stream_active(self, index: int, char: Any, value: Any) -> None:
        """Update the authenticated controller's individual RTP setting."""
        assert self._hksv is not None
        if not self._hksv.ready or value not in (0, 1):
            char.set_value(int(self._hksv.stream_active(index)), should_notify=False)
            raise ValueError("Invalid stream active state")
        self._hksv.set_stream_active(index, value)
        char.set_value(value)

    @callback
    def _hksv_stop_live(self, stream_idx: int | None = None) -> None:
        """Stop one disabled stream slot or every stream if the camera is off."""
        for session_info in list(self.sessions.values()):
            if stream_idx is not None and session_info.get("stream_idx") != stream_idx:
                continue
            self.hass.async_create_background_task(
                self.stop_stream(session_info), "homekit.camera-stop-stream"
            )

    async def _hksv_capabilities_changed(self) -> None:
        """Publish a changed recording capability after the driver has started."""
        await self.hass.async_add_executor_job(self.driver.config_changed)

    @pyhap_callback  # type: ignore[untyped-decorator]
    @callback
    @override
    def run(self) -> None:
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        if self._char_motion_detected:
            assert self.linked_motion_sensor
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    self.linked_motion_sensor,
                    self._async_update_motion_state_event,
                    job_type=HassJobType.Callback,
                )
            )

        if self._hksv:
            self._subscriptions.append(
                async_track_entity_registry_updated_event(
                    self.hass,
                    self.entity_id,
                    self._async_camera_registry_updated,
                    job_type=HassJobType.Callback,
                )
            )
            self._hksv_start_task = self.hass.async_create_background_task(
                self._hksv.start(), "homekit.hksv-start"
            )
        super().run()

    @callback
    def _async_camera_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Reconcile recording after the camera's orientation changes."""
        if event.data["action"] != "update" or "options" not in event.data["changes"]:
            return
        entry = er.async_get(self.hass).async_get(self.entity_id)
        if entry is None:
            return
        old_options = event.data["changes"]["options"]
        old_orientation = old_options.get(camera.DOMAIN, {}).get(
            PREF_ORIENTATION, Orientation.NO_TRANSFORM
        )
        camera_options = entry.options.get(camera.DOMAIN)
        new_orientation = (
            camera_options.get(PREF_ORIENTATION, Orientation.NO_TRANSFORM)
            if camera_options is not None
            else Orientation.NO_TRANSFORM
        )
        if old_orientation != new_orientation:
            # CameraPreferences updates the shared settings after the registry event.
            self.hass.loop.call_soon(self._async_camera_orientation_changed)

    @callback
    def _async_camera_orientation_changed(self) -> None:
        """Notify the controller after the preference update completes."""
        if self._hksv and not self._camera_stopping:
            self._hksv.source_orientation_changed()

    @callback
    def _async_update_motion_state_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        if not state_changed_event_is_same_state(event) and (
            new_state := event.data["new_state"]
        ):
            self._async_update_motion_state(event.data["old_state"], new_state)

    @callback
    def _async_update_motion_state(
        self, old_state: State | None, new_state: State
    ) -> None:
        """Handle link motion sensor state change to update HomeKit value."""
        state = new_state.state
        char = self._char_motion_detected
        assert char is not None
        if self.motion_is_event:
            if (
                old_state is None
                or old_state.state == STATE_UNAVAILABLE
                or state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            ):
                return
            _LOGGER.debug(
                "%s: Set linked motion %s sensor to True/False",
                self.entity_id,
                self.linked_motion_sensor,
            )
            if self._hksv is not None:
                self._hksv.motion(True)
                self._hksv.motion(False)
            char.set_value(True)
            if self._hksv is None:
                char.set_value(False)
                return
            if previous := getattr(self, "_motion_event_reset", None):
                previous.cancel()
            self._motion_event_reset = self.hass.loop.call_later(
                1.0, char.set_value, False
            )
            return

        detected = state == STATE_ON
        if self._hksv is not None:
            self._hksv.motion(detected)
        if char.value == detected:
            return

        char.set_value(detected)
        _LOGGER.debug(
            "%s: Set linked motion %s sensor to %d",
            self.entity_id,
            self.linked_motion_sensor,
            detected,
        )

    @callback
    @override
    def async_update_state(self, new_state: State | None) -> None:
        """Handle state change to update HomeKit value."""

    async def _async_get_stream_source(self) -> str | None:
        """Find the camera stream source url."""
        stream_source: str | None = self.config.get(CONF_STREAM_SOURCE)
        if stream_source:
            return stream_source
        try:
            stream_source = await camera.async_get_stream_source(
                self.hass, self.entity_id
            )
        except Exception:
            _LOGGER.exception(
                "Failed to get stream source - this could be a transient error or your"
                " camera might not be compatible with HomeKit yet"
            )
        return stream_source

    async def _async_get_hksv_source(self) -> SharedCameraStream:
        """Attach to the audio-capable shared Home Assistant stream."""
        if self.config.get(CONF_STREAM_SOURCE):
            raise ValueError(
                "Explicit stream_source cannot use the shared camera stream"
            )
        return await SharedCameraStream.open(
            self.hass,
            self.entity_id,
            receive_timestamps=self.config.get(
                CONF_SECURE_VIDEO_RECEIVE_TIMESTAMPS,
                DEFAULT_SECURE_VIDEO_RECEIVE_TIMESTAMPS,
            ),
        )

    def _live_allowed(self, session_info: dict[str, Any]) -> bool:
        """Apply the current operating and per-slot permissions."""
        return self._hksv is None or (
            self._hksv.privacy_ready
            and self._hksv.camera_active
            and self._hksv.stream_active(session_info["stream_idx"])
        )

    async def _live_video_parameters(
        self, stream_config: dict[str, Any], shared: SharedCameraStream | None = None
    ) -> tuple[str, str, str, HardwareEncoder | None]:
        """Choose a verified compatible video path for the selected stream."""
        input_source = "-readrate 1 -i pipe:0"
        video_codec = self.config[CONF_VIDEO_CODEC]
        profile = int.from_bytes(stream_config["v_profile_id"], "big")
        level = int.from_bytes(stream_config["v_level"], "big")
        width, height, fps = (stream_config[key] for key in ("width", "height", "fps"))
        if profile not in range(3) or level not in range(3):
            raise ValueError("Unsupported HomeKit live video parameters")
        filters = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )
        preserve_source = bool(self._hksv and self._hksv.preserve_source)
        if video_codec != "copy" and not preserve_source:
            orientation = (
                shared.orientation if shared is not None else Orientation.NO_TRANSFORM
            )
            if orientation != Orientation.NO_TRANSFORM:
                input_source = "-noautorotate " + input_source
                filters = f"{orientation_video_filter(orientation)},{filters}"
            profile_name = self.config[CONF_VIDEO_PROFILE_NAMES][profile]
            encoder_options = ["-vf", filters]
            if video_codec == "libx264":
                encoder_options += ["-preset", "veryfast"]
            encoder_options += [
                "-profile:v",
                profile_name,
                "-level:v",
                ("3.1", "3.2", "4.0")[level],
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
            ]
            return input_source, video_codec, shlex.join(encoder_options) + " ", None
        try:
            observed = (
                await self._hksv.observe_live_source(shared) if self._hksv else None
            )
        except Exception:  # noqa: BLE001 - software fallback preserves live
            _LOGGER.warning("%s: Could not inspect HomeKit live source", self.entity_id)
            observed = None
        orientation = (
            shared.orientation if shared is not None else Orientation.NO_TRANSFORM
        )
        if orientation != Orientation.NO_TRANSFORM:
            input_source = "-noautorotate " + input_source
            filters = f"{orientation_video_filter(orientation)},{filters}"
        if (
            orientation == Orientation.NO_TRANSFORM
            and observed is not None
            and (
                (
                    preserve_source
                    and observed.video_codec == "h264"
                    and observed.h264_profile_idc in (66, 77, 100)
                    and observed.width > 0
                    and observed.height > 0
                    and observed.observation_seconds >= 2
                )
                or live_video_compatible(
                    observed,
                    profile,
                    level,
                    width,
                    height,
                    fps,
                    stream_config["v_max_bitrate"],
                )
            )
        ):
            return input_source, "copy", "-bsf:v h264_mp4toannexb ", None
        try:
            async with asyncio.timeout(4):
                hardware = await _HARDWARE_PROBE.select(
                    self._ffmpeg.binary, profile, level, width, height, fps
                )
        except Exception:  # noqa: BLE001 - software fallback preserves live
            hardware = None
        if hardware:
            filters += f",{hardware.video_filter}"
            input_source = shlex.join(hardware.global_args) + " " + input_source
            options = shlex.join(("-vf", filters, *hardware.output_args)) + " "
            return input_source, hardware.codec, options, hardware
        options = (
            shlex.join(
                (
                    "-vf",
                    filters,
                    "-preset",
                    "veryfast",
                    "-tune",
                    "zerolatency",
                    "-pix_fmt",
                    "yuv420p",
                    "-profile:v",
                    ("baseline", "main", "high")[profile],
                    "-level:v",
                    ("3.1", "3.2", "4.0")[level],
                )
            )
            + " "
        )
        return input_source, "libx264", options, None

    def _live_audio_parameters(
        self, stream_config: dict[str, Any]
    ) -> tuple[str, str, str]:
        """Encode the shared AAC/MP3 input to the advertised Opus codec."""
        audio_codec = self.config[CONF_AUDIO_CODEC]
        if audio_codec == "copy":
            audio_codec = "libopus"
        if audio_codec == "libopus":
            return (
                audio_codec,
                "-application lowdelay ",
                f"-frame_duration {stream_config.get('a_packet_time', 20)} ",
            )
        return audio_codec, "", ""

    async def _direct_live_parameters(
        self, stream_config: dict[str, Any]
    ) -> tuple[str, str, str, str, str, str] | None:
        """Prepare the configured direct stream using normal HomeKit behavior."""
        if not (input_source := await self._async_get_stream_source()):
            _LOGGER.error("Camera has no stream source")
            return None
        if "-i " not in input_source:
            input_source = "-i " + input_source
        video_codec = self.config[CONF_VIDEO_CODEC]
        video_options = ""
        if video_codec != "copy":
            profile = int.from_bytes(stream_config["v_profile_id"], "big")
            video_options = (
                f"-profile:v {self.config[CONF_VIDEO_PROFILE_NAMES][profile]} "
            )
        video_options += "-tune zerolatency -pix_fmt yuv420p "
        audio_codec = self.config[CONF_AUDIO_CODEC]
        audio_application = audio_frame_duration = ""
        if audio_codec == "libopus":
            audio_application = "-application lowdelay "
            audio_frame_duration = (
                f"-frame_duration {stream_config.get('a_packet_time', 20)} "
            )
        return (
            input_source,
            video_codec,
            video_options,
            audio_codec,
            audio_application,
            audio_frame_duration,
        )

    async def _open_live_stream(
        self,
        session_info: dict[str, Any],
        input_source: str,
        output: str,
        audio_proxy: AudioProxy | None,
        shared: SharedCameraStream | None,
    ) -> tuple[HAFFmpeg, SharedCameraStream | None] | None:
        """Open the live encoder using the session input."""
        if shared:
            if not self._live_allowed(session_info):
                if audio_proxy:
                    await audio_proxy.async_stop()
                return None
            try:
                burst = await shared.prepare_live_input()
            except BaseException:
                if audio_proxy:
                    await audio_proxy.async_stop()
                raise
            if not self._live_allowed(session_info):
                if audio_proxy:
                    await audio_proxy.async_stop()
                return None
            if burst > 0:
                input_source = input_source.replace(
                    "-i pipe:0", f"-readrate_initial_burst {burst:.3f} -i pipe:0"
                )
        stream = HAFFmpeg(self._ffmpeg.binary)
        try:
            opened = await stream.open(
                cmd=[],
                input_source=input_source,
                output=output,
                extra_cmd="-hide_banner -nostats",
                stderr_pipe=True,
                stdout_pipe=False,
            )
        except BaseException:
            if audio_proxy:
                await audio_proxy.async_stop()
            raise
        if not opened:
            _LOGGER.error("Failed to open ffmpeg stream")
            if audio_proxy:
                await audio_proxy.async_stop()
            return None

        if not self._live_allowed(session_info):
            await stream.close(timeout=1)
            if audio_proxy:
                await audio_proxy.async_stop()
            return None

        return stream, shared

    async def start_stream(
        self, session_info: dict[str, Any], stream_config: dict[str, Any]
    ) -> bool:
        """Start a new stream with the given configuration."""
        if not self._live_allowed(session_info):
            raise RuntimeError("HomeKit camera stream is disabled")
        _LOGGER.debug("[%s] Starting HomeKit live stream", session_info["id"])
        if self._hksv:
            profile_value = stream_config.get("v_profile_id")
            level_value = stream_config.get("v_level")
            _LOGGER.info(
                "%s: HomeKit live selection profile=%s level=%s %sx%s fps=%s audio_rate=%s",
                self.entity_id,
                int.from_bytes(profile_value, "big")
                if isinstance(profile_value, bytes)
                else None,
                int.from_bytes(level_value, "big")
                if isinstance(level_value, bytes)
                else None,
                stream_config.get("width"),
                stream_config.get("height"),
                stream_config.get("fps"),
                stream_config.get("a_sample_rate"),
            )
        shared = None
        if self._hksv:
            try:
                shared = await self._async_get_hksv_source()
            except ValueError, RuntimeError, OSError, HomeAssistantError:
                _LOGGER.warning(
                    "%s: Shared camera source is unavailable", self.entity_id
                )
                return False
        try:
            return await self._start_stream_with_source(
                session_info, stream_config, shared
            )
        finally:
            if shared and session_info.get(FFMPEG_SHARED) is not shared:
                await shared.close()

    async def _start_stream_with_source(
        self,
        session_info: dict[str, Any],
        stream_config: dict[str, Any],
        shared: SharedCameraStream | None,
    ) -> bool:
        """Start a live session using its acquired shared source."""
        if not self._live_allowed(session_info):
            return False
        if self._hksv:
            (
                input_source,
                video_codec,
                video_options,
                hardware,
            ) = await self._live_video_parameters(stream_config, shared)
            if not self._live_allowed(session_info):
                return False
            audio_codec, audio_application, audio_frame_duration = (
                self._live_audio_parameters(stream_config)
            )
        else:
            parameters = await self._direct_live_parameters(stream_config)
            if parameters is None:
                return False
            (
                input_source,
                video_codec,
                video_options,
                audio_codec,
                audio_application,
                audio_frame_duration,
            ) = parameters
            hardware = None
        # Start audio proxy to convert Opus RTP timestamps from 48kHz
        # (FFmpeg's hardcoded Opus RTP clock rate per RFC 7587) to the
        # sample rate negotiated by HomeKit (typically 16kHz).
        # a_sample_rate is in kHz (e.g. 16 for 16000 Hz) from pyhap TLV.
        audio_proxy: AudioProxy | None = None
        if self.config[CONF_SUPPORT_AUDIO]:
            audio_proxy = AudioProxy(
                dest_addr=stream_config["address"],
                dest_port=stream_config["a_port"],
                srtp_key_b64=stream_config["a_srtp_key"],
                target_clock_rate=stream_config["a_sample_rate"] * 1000,
            )
            await audio_proxy.async_start()
            if not audio_proxy.local_port:
                _LOGGER.error(
                    "[%s] Audio proxy failed to start",
                    self.display_name,
                )
                await audio_proxy.async_stop()
                audio_proxy = None

        output_vars = stream_config.copy()
        output_vars.update(
            {
                "v_options": video_options,
                "v_bufsize": stream_config["v_max_bitrate"] * 4,
                "v_map": self.config[CONF_VIDEO_MAP],
                "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
                "v_codec": video_codec,
                "a_bufsize": stream_config["a_max_bitrate"] * 4,
                "a_map": self.config[CONF_AUDIO_MAP],
                "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
                "a_encoder": audio_codec,
                "a_application": audio_application,
                "a_frame_duration": audio_frame_duration,
                "a_proxy_port": audio_proxy.local_port if audio_proxy else 0,
            }
        )
        if not self._live_allowed(session_info):
            if audio_proxy:
                await audio_proxy.async_stop()
            return False
        output_vars["v_rate_control"] = (
            ""
            if self._hksv and video_codec == "copy"
            else (
                f"-r {stream_config['fps']} "
                f"-b:v {stream_config['v_max_bitrate']}k "
                f"-bufsize {output_vars['v_bufsize']}k "
                f"-maxrate {stream_config['v_max_bitrate']}k "
            )
        )
        output = VIDEO_OUTPUT.format(**output_vars)
        if self._hksv and self._hksv.preserve_source and video_codec == "copy":
            if TYPE_CHECKING:
                assert shared is not None
            native = await self._start_native_live(
                session_info, stream_config, audio_proxy, output_vars, shared
            )
            if native is not None:
                return native
        if not self._hksv and self.config[CONF_SUPPORT_AUDIO]:
            output = output + " " + AUDIO_OUTPUT.format(**output_vars)
        opened = await self._open_live_stream(
            session_info, input_source, output, audio_proxy, shared
        )
        if opened is None:
            return False
        stream, shared = opened

        _LOGGER.debug(
            "[%s] Started stream process - PID %d",
            session_info["id"],
            stream.process.pid,
        )

        session_info["stream"] = stream
        session_info[FFMPEG_PID] = stream.process.pid
        if shared:
            session_info[FFMPEG_SHARED] = shared
            session_info[FFMPEG_INPUT_TASK] = create_eager_task(
                self._feed_shared_live(stream, shared)
            )
        if shared and audio_proxy and self.config[CONF_SUPPORT_AUDIO]:
            session_info[FFMPEG_AUDIO_TASK] = create_eager_task(
                self._run_shared_audio(
                    session_info, shared, AUDIO_OUTPUT.format(**output_vars)
                )
            )
        if hardware is not None:
            session_info[FFMPEG_LIVE_HARDWARE] = hardware.codec
        session_info[AUDIO_PROXY] = audio_proxy

        try:
            stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)
        except BaseException:
            session_info.pop(FFMPEG_SHARED, None)
            await self._release_shared_live(session_info)
            await stream.close(timeout=1)
            if audio_proxy:
                await audio_proxy.async_stop()
                session_info.pop(AUDIO_PROXY, None)
            raise

        async def watch_session(_: Any) -> None:
            await self._async_ffmpeg_watch(session_info["id"])

        session_info[FFMPEG_LOGGER] = create_eager_task(
            self._async_log_stderr_stream(stderr_reader, session_info)
        )
        session_info[FFMPEG_WATCHER] = async_track_time_interval(
            self.hass,
            watch_session,
            FFMPEG_WATCH_INTERVAL,
        )

        return await self._async_ffmpeg_watch(session_info["id"])

    async def _start_native_live(
        self,
        session_info: dict[str, Any],
        stream_config: dict[str, Any],
        audio_proxy: AudioProxy | None,
        output_vars: dict[str, Any],
        shared: SharedCameraStream,
    ) -> bool | None:
        """Start one native SRTP sender, falling back if initialization fails."""
        task = None
        try:
            if not self._live_allowed(session_info):
                if audio_proxy:
                    await audio_proxy.async_stop()
                return False
            burst = await shared.prepare_live_input()
            if not self._live_allowed(session_info):
                if audio_proxy:
                    await audio_proxy.async_stop()
                return False
            sender = NativeVideoSender(
                stream_config["v_srtp_key"],
                stream_config["v_ssrc"],
                stream_config["address"],
                stream_config["v_port"],
                self.config[CONF_VIDEO_PACKET_SIZE],
                burst,
                rtcp_interval=stream_config.get("v_rtcp_interval", 5.0),
            )
            task = create_eager_task(sender.run(shared.live_parts()))
            await asyncio.sleep(0)
            if not self._live_allowed(session_info):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if audio_proxy:
                    await audio_proxy.async_stop()
                return False
            if task.done():
                await task
                _LOGGER.warning(
                    "%s: Native live video stopped during startup; using FFmpeg",
                    self.entity_id,
                )
                return None
        except asyncio.CancelledError:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if audio_proxy:
                await audio_proxy.async_stop()
            raise
        except Exception:  # noqa: BLE001 - retain the established FFmpeg fallback
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            _LOGGER.warning(
                "%s: Native live video unavailable; using FFmpeg", self.entity_id
            )
            return None
        session_info[FFMPEG_SHARED] = shared
        session_info[NATIVE_VIDEO_TASK] = task
        session_info[AUDIO_PROXY] = audio_proxy
        if audio_proxy and self.config[CONF_SUPPORT_AUDIO]:
            session_info[FFMPEG_AUDIO_TASK] = create_eager_task(
                self._run_shared_audio(
                    session_info, shared, AUDIO_OUTPUT.format(**output_vars)
                )
            )

        async def watch_session(_: Any) -> None:
            await self._async_ffmpeg_watch(session_info["id"])

        session_info[FFMPEG_WATCHER] = async_track_time_interval(
            self.hass, watch_session, FFMPEG_WATCH_INTERVAL
        )
        return True

    async def _feed_shared_live(self, stream: HAFFmpeg, shared: Any) -> None:
        """Feed bounded shared parts to this session's FFmpeg process."""
        process = stream.process
        try:
            async for chunk in shared.live_parts():
                process.stdin.write(chunk)
                async with asyncio.timeout(5):
                    await process.stdin.drain()
        except BrokenPipeError, ConnectionError, TimeoutError, ValueError:
            _LOGGER.warning("%s: Shared live stream interrupted", self.entity_id)
        finally:
            if process and process.stdin:
                process.stdin.close()

    async def _run_shared_audio(
        self,
        session_info: dict[str, Any],
        video_shared: SharedCameraStream,
        output: str,
    ) -> None:
        """Feed the audio process independently of the video process."""
        shared = None
        stream = None
        logger = None
        try:
            shared = await self._async_get_hksv_source()
            if not self._live_allowed(session_info):
                return
            if not shared.follow_live_start(video_shared):
                async with asyncio.timeout(20):
                    await video_shared.wait_live_start()
                if not self._live_allowed(session_info) or not shared.follow_live_start(
                    video_shared
                ):
                    return
            stream = HAFFmpeg(self._ffmpeg.binary)
            burst = shared.live_initial_burst
            audio_input = "-readrate 1 "
            if burst > 0:
                audio_input += f"-readrate_initial_burst {burst:.3f} "
            audio_input += "-i pipe:0"
            if not await stream.open(
                cmd=[],
                input_source=audio_input,
                output=output,
                extra_cmd="-hide_banner -nostats",
                stderr_pipe=True,
                stdout_pipe=False,
            ):
                return
            if not self._live_allowed(session_info):
                return
            reader = await stream.get_reader(source=FFMPEG_STDERR)

            async def drain_stderr() -> None:
                while await reader.read(4096):
                    pass

            logger = create_eager_task(drain_stderr())
            await self._feed_shared_live(stream, shared)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - audio failure must not interrupt video
            _LOGGER.warning("%s: Shared live audio interrupted", self.entity_id)
        finally:
            if logger:
                logger.cancel()
                await asyncio.gather(logger, return_exceptions=True)
            try:
                if stream:
                    await stream.close(timeout=1)
            finally:
                if shared:
                    await shared.close()

    async def _release_shared_live(self, session_info: dict[str, Any]) -> None:
        """Release the session input independently from recording."""
        if task := session_info.pop(NATIVE_VIDEO_TASK, None):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if task := session_info.pop(FFMPEG_AUDIO_TASK, None):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if task := session_info.pop(FFMPEG_INPUT_TASK, None):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if shared := session_info.pop(FFMPEG_SHARED, None):
            await shared.close()

    async def _async_log_stderr_stream(
        self, stderr_reader: asyncio.StreamReader, session_info: dict[str, Any]
    ) -> None:
        """Keep only bounded, non-sensitive FFmpeg error categories."""
        categories: set[str] = set()
        session_info[FFMPEG_DIAGNOSTICS] = categories
        patterns = (
            ("authentication", (b"401 unauthorized", b"unauthorized")),
            ("input_not_found", (b"404 not found", b"server returned 404")),
            ("connection_refused", (b"connection refused",)),
            ("timeout", (b"timed out", b"connection timeout")),
            (
                "resource_busy",
                (b"resource temporarily unavailable", b"server returned 453"),
            ),
            (
                "invalid_input",
                (b"invalid data found", b"could not find codec parameters"),
            ),
            (
                "encoder",
                (
                    b"error initializing output stream",
                    b"error while opening encoder",
                    b"failed to configure output pad",
                ),
            ),
            (
                "address_or_protocol",
                (
                    b"address family not supported",
                    b"address already in use",
                    b"bind failed",
                    b"network is unreachable",
                    b"no route to host",
                    b"getaddrinfo",
                    b"invalid ipv6",
                    b"invalid argument",
                    b"protocol not found",
                ),
            ),
            (
                "network_io",
                (b"input/output error", b"connection reset by peer", b"broken pipe"),
            ),
        )
        tail = b""
        while chunk := await stderr_reader.read(4096):
            scan = (tail + chunk).lower()
            for category, terms in patterns:
                if any(term in scan for term in terms):
                    categories.add(category)
            tail = scan[-128:]

    async def _async_ffmpeg_watch(self, session_id: str) -> bool:
        """Check to make sure ffmpeg is still running and cleanup if not."""
        session_info = self.sessions[session_id]
        if task := session_info.get(NATIVE_VIDEO_TASK):
            if not task.done():
                return True
            _LOGGER.warning("%s: Native HomeKit live stream ended", self.entity_id)
            self._async_stop_ffmpeg_watch(session_id)
            await self._release_shared_live(session_info)
            if proxy := session_info.pop(AUDIO_PROXY, None):
                await proxy.async_stop()
            self.set_streaming_available(session_info["stream_idx"])
            return False
        ffmpeg_pid = session_info[FFMPEG_PID]
        if pid_is_alive(ffmpeg_pid):
            return True
        logger_task = session_info.get(FFMPEG_LOGGER)
        if logger_task is not None:
            try:
                async with asyncio.timeout(0.5):
                    await asyncio.shield(logger_task)
            except TimeoutError:
                pass
        diagnostics = sorted(session_info.get(FFMPEG_DIAGNOSTICS, ()))
        if codec := session_info.pop(FFMPEG_LIVE_HARDWARE, None):
            _HARDWARE_PROBE.report_failure(codec)
        stream = session_info.get("stream")
        exit_code = stream.process.returncode if stream is not None else None
        _LOGGER.warning(
            "%s: HomeKit live stream ended unexpectedly (exit=%s, categories=%s)",
            self.entity_id,
            exit_code,
            diagnostics or ["unclassified"],
        )
        self._async_stop_ffmpeg_watch(session_id)
        await self._release_shared_live(session_info)
        if proxy := session_info.pop(AUDIO_PROXY, None):
            await proxy.async_stop()
        self.set_streaming_available(session_info["stream_idx"])
        return False

    @callback
    def _async_stop_ffmpeg_watch(self, session_id: str) -> None:
        """Cleanup a streaming session after stopping."""
        if FFMPEG_WATCHER not in self.sessions[session_id]:
            return
        self.sessions[session_id].pop(FFMPEG_WATCHER)()
        if logger := self.sessions[session_id].pop(FFMPEG_LOGGER, None):
            logger.cancel()

    @callback
    @override
    def async_stop(self) -> None:
        """Stop any streams when the accessory is stopped."""
        if motion_reset := getattr(self, "_motion_event_reset", None):
            motion_reset.cancel()
            del self._motion_event_reset
        if self._camera_stopping:
            return
        self._camera_stopping = True
        for session_info in self.sessions.values():
            self._camera_stream_stop_tasks.append(
                self.hass.async_create_background_task(
                    self.stop_stream(session_info), "homekit.camera-stop-stream"
                )
            )
        super().async_stop()

    @override
    async def stop(self) -> None:
        """Stop recording, HDS and live streams before accessory teardown."""
        if self._camera_stop_task is None:
            self._camera_stop_task = asyncio.create_task(self._async_finish_stop())
        await asyncio.shield(self._camera_stop_task)

    async def _async_finish_stop(self) -> None:
        """Own cleanup independently of the caller's cancellation."""
        if self._hksv_start_task:
            self._hksv_start_task.cancel()
            await asyncio.gather(self._hksv_start_task, return_exceptions=True)
        await super().stop()
        try:
            if self._hksv:
                await self._hksv.close()
        finally:
            if self._camera_stream_stop_tasks:
                await asyncio.gather(*self._camera_stream_stop_tasks)

    async def stop_stream(self, session_info: dict[str, Any]) -> None:
        """Stop the stream for the given ``session_id``."""
        session_id = session_info["id"]
        if NATIVE_VIDEO_TASK in session_info:
            self._async_stop_ffmpeg_watch(session_id)
        shared_input = FFMPEG_SHARED in session_info
        await self._release_shared_live(session_info)
        if proxy := session_info.pop(AUDIO_PROXY, None):
            await proxy.async_stop()

        if not (stream := session_info.get("stream")):
            _LOGGER.debug("No stream for session ID %s", session_id)
            return

        self._async_stop_ffmpeg_watch(session_id)

        if not pid_is_alive(stream.process.pid):
            _LOGGER.warning("[%s] Stream already stopped", session_id)
            return

        if not shared_input:
            for shutdown_method in ("close", "kill"):
                try:
                    await getattr(stream, shutdown_method)()
                except Exception:
                    _LOGGER.exception(
                        "[%s] Failed to %s stream", session_id, shutdown_method
                    )
                else:
                    return
            return

        process = stream.process
        try:
            async with asyncio.timeout(3):
                await process.wait()
        except TimeoutError:
            try:
                process.terminate()
                async with asyncio.timeout(2):
                    await process.wait()
            except TimeoutError:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass

    async def reconfigure_stream(
        self, session_info: dict[str, Any], stream_config: dict[str, Any]
    ) -> bool:
        """Reconfigure the stream so that it uses the given ``stream_config``."""
        return True

    async def async_get_snapshot(self, image_size: dict[str, int]) -> bytes:
        """Return a jpeg of a snapshot from the camera."""
        if self._hksv is None:
            camera_image = await camera.async_get_image(
                self.hass,
                self.entity_id,
                width=image_size["image-width"],
                height=image_size["image-height"],
            )
            return camera_image.content
        if self._hksv and not self._hksv.snapshot_allowed(image_size.get("reason")):
            raise RuntimeError("HomeKit camera snapshot is disabled")
        async with asyncio.timeout(SNAPSHOT_TIMEOUT):
            shared = await self._async_get_hksv_source()
            try:
                image = await shared.image(
                    image_size["image-width"], image_size["image-height"]
                )
            finally:
                await shared.close()
        if self._hksv and not self._hksv.snapshot_allowed(image_size.get("reason")):
            raise RuntimeError("HomeKit camera snapshot is disabled")
        if image is None:
            raise RuntimeError("HomeKit camera snapshot is unavailable")
        return image
