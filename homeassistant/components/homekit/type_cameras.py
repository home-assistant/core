"""Class to hold all camera accessories."""

import asyncio
from collections import deque
from collections.abc import AsyncGenerator, Coroutine
from dataclasses import asdict
from datetime import datetime, timedelta
import logging
import math
import re
import shlex
from typing import TYPE_CHECKING, Any, override

from haffmpeg.core import FFMPEG_STDERR, HAFFmpeg
from homekit_audio_proxy import AudioProxy
from pyhap.camera import (
    VIDEO_CODEC_PARAM_LEVEL_TYPES,
    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES,
    Camera as PyhapCamera,
)
from pyhap.const import CATEGORY_CAMERA, STANDALONE_AID
from pyhap.hds_recording import RecordingPacket, RecordingReason, fmp4_recording_packets
from pyhap.hksv_recording import (
    AudioCodecConfiguration,
    AudioSampleRate,
    SelectedRecordingConfiguration,
    SupportedRecordingConfiguration,
    VideoAttributes,
    VideoCodecConfiguration,
)
from pyhap.util import callback as pyhap_callback

from homeassistant.components import camera
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJobType,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util.async_ import create_eager_task

from .accessories import TYPES, HomeDriver
from .const import (
    CAMERA_MODE_SECURE_VIDEO,
    CHAR_MOTION_DETECTED,
    CONF_AUDIO_CODEC,
    CONF_AUDIO_MAP,
    CONF_AUDIO_PACKET_SIZE,
    CONF_CAMERA_MODE,
    CONF_LINKED_MOTION_SENSOR,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
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
    DEFAULT_CAMERA_MODE,
    DEFAULT_MAX_FPS,
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_STREAM_COUNT,
    DEFAULT_SUPPORT_AUDIO,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_MAP,
    DEFAULT_VIDEO_PACKET_SIZE,
    DEFAULT_VIDEO_PROFILE_NAMES,
    SERV_MOTION_SENSOR,
    VIDEO_CODEC_COPY,
    VIDEO_CODEC_LIBX264,
)
from .doorbell import HomeDoorbellAccessory
from .util import pid_is_alive, state_changed_event_is_same_state

_LOGGER = logging.getLogger(__name__)


VIDEO_OUTPUT = (
    "-map {v_map} -an "
    "-c:v {v_codec} "
    "{v_profile}"
    "-tune zerolatency -pix_fmt yuv420p "
    "-r {fps} "
    "-b:v {v_max_bitrate}k -bufsize {v_bufsize}k -maxrate {v_max_bitrate}k "
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

RECORDING_LEVELS = ("3.1", "3.2", "4.0")

RECORDING_SAMPLE_RATES = {
    AudioSampleRate.KHZ_8: 8000,
    AudioSampleRate.KHZ_16: 16000,
    AudioSampleRate.KHZ_24: 24000,
    AudioSampleRate.KHZ_32: 32000,
    AudioSampleRate.KHZ_44_1: 44100,
    AudioSampleRate.KHZ_48: 48000,
}

# A recording ends when ffmpeg delivers no fragment for this long. Covers
# connecting to the camera and waiting for its next keyframe.
RECORDING_TIMEOUT = 30
RECORDING_STDERR_LINES = 10
# ffmpeg exits right after its output ends, a hang must not block the recording.
RECORDING_EXIT_TIMEOUT = 5
# ffmpeg errors can quote the input URL, which may carry credentials or tokens.
RECORDING_STDERR_URL = re.compile(rb"[A-Za-z][A-Za-z0-9+.-]*://\S*[^\s:]")

RECORDING_OUTPUT = (
    "-f mp4 -movflags frag_keyframe+empty_moov+default_base_moof+skip_trailer -"
)

# The sizes a home hub selects recordings in, at exactly 30, 24 or 15 fps.
RECORDING_RESOLUTIONS = (
    (1920, 1080),
    (1280, 720),
    (1600, 1200),
    (1440, 1080),
    (1280, 960),
    (1024, 768),
)
RECORDING_FRAME_RATES = (30, 24, 15)
# The init segment comes first, video starts with the second packet.
RECORDING_FIRST_VIDEO_PACKET = 2
# Time for the stderr reader to collect the last lines after ffmpeg exited.
RECORDING_STDERR_DRAIN_SECONDS = 1


def with_input_flag(input_source: str) -> str:
    """Return the ffmpeg input arguments for a stream source."""
    if "-i " not in input_source:
        return "-i " + input_source
    return input_source


def recording_ffmpeg_args(
    config: dict[str, Any],
    selected: SelectedRecordingConfiguration,
    input_source: str,
    audio_active: bool,
) -> tuple[str, str]:
    """Return the ffmpeg input and output arguments for a recording."""
    video = selected.video
    attributes = video.attributes[0]
    video_codec = config[CONF_VIDEO_CODEC]
    input_args = shlex.split(with_input_flag(input_source))
    if video_codec == VIDEO_CODEC_COPY:
        # Fragments follow the camera GOP, the camera sets the keyframe interval.
        video_args = f"-map {config[CONF_VIDEO_MAP]} -c:v copy"
    else:
        fps = attributes.frame_rate
        iframe_seconds = video.iframe_interval_ms / 1000
        encoder_args = ""
        if video_codec == VIDEO_CODEC_LIBX264:
            # Hardware encoders take no level string.
            encoder_args = (
                f"-level:v {RECORDING_LEVELS[int(video.level)]} "
                "-preset veryfast -tune zerolatency "
            )
        # A second -vf would replace source filters such as a flip, so they run
        # first, in the reverse order ha-ffmpeg also gives them in live streams.
        filters: list[str] = []
        source_args: list[str] = []
        tokens = iter(input_args)
        for token in tokens:
            if token in ("-vf", "-filter:v"):
                if (value := next(tokens, None)) is None:
                    raise ValueError(f"{token} without a filter")
                filters.insert(0, value)
            else:
                source_args.append(token)
        input_args = source_args
        # The hub expects exactly the selected size, other aspect ratios are padded.
        filters.append(
            f"scale={attributes.width}:{attributes.height}:"
            "force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={attributes.width}:{attributes.height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
        video_args = (
            f"-map {config[CONF_VIDEO_MAP]} -c:v {video_codec} "
            f"-profile:v {config[CONF_VIDEO_PROFILE_NAMES][int(video.profile)]} "
            f"{encoder_args}-pix_fmt yuv420p "
            f"-vf {shlex.quote(','.join(filters))} "
            f"-r {fps} -b:v {video.bitrate_kbps}k -maxrate {video.bitrate_kbps}k "
            f"-bufsize {video.bitrate_kbps * 2}k -bf 0 "
            f"-g {math.ceil(fps * iframe_seconds)} "
            f"-force_key_frames expr:gte(t,n_forced*{iframe_seconds:g}) "
            # Without it scene cuts add keyframes and split fragments.
            "-sc_threshold 0"
        )
    audio = selected.audio
    sample_rate = RECORDING_SAMPLE_RATES[audio.sample_rate]
    if audio_active and config[CONF_SUPPORT_AUDIO]:
        audio_input = ""
        audio_map = config[CONF_AUDIO_MAP]
    else:
        # The hub expects an audio track, so a silent one stands in.
        audio_input = (
            f" -f lavfi -i anullsrc=channel_layout=mono:sample_rate={sample_rate}"
        )
        # The silent input comes after all inputs of the stream source.
        audio_map = f"{input_args.count('-i')}:a:0"
    audio_args = (
        f"-map {audio_map} -c:a aac -profile:a aac_low -ac {audio.channels} "
        f"-ar {sample_rate} -b:a {audio.max_audio_bitrate_kbps}k"
    )
    return (
        shlex.join(input_args) + audio_input,
        f"{video_args} {audio_args} -shortest {RECORDING_OUTPUT}",
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
# pyhap coalesces events per characteristic, so a motion event must stay
# detected long enough for HomeKit to receive it.
MOTION_EVENT_RESET_SECONDS = 10
FFMPEG_LOGGER = "ffmpeg_logger"
FFMPEG_WATCHER = "ffmpeg_watcher"
FFMPEG_PID = "ffmpeg_pid"
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
    CONF_CAMERA_MODE: DEFAULT_CAMERA_MODE,
}


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

        self._recording_problem: str | None = None

        self.secure_video = False
        self._recording_attributes: list[VideoAttributes] = []
        if config[CONF_CAMERA_MODE] == CAMERA_MODE_SECURE_VIDEO:
            if not config.get(CONF_LINKED_MOTION_SENSOR):
                _LOGGER.warning(
                    "%s: HomeKit Secure Video needs a linked motion sensor", entity_id
                )
            elif aid != STANDALONE_AID:
                _LOGGER.warning(
                    "%s: HomeKit Secure Video needs the camera in accessory mode",
                    entity_id,
                )
            else:
                self.secure_video = True
                fps = next(
                    (rate for rate in RECORDING_FRAME_RATES if rate <= max_fps),
                    RECORDING_FRAME_RATES[-1],
                )
                # Recordings are scaled to the selected size, streaming limits do
                # not apply.
                self._recording_attributes = [
                    VideoAttributes(height, width, fps)
                    if max_height > max_width
                    else VideoAttributes(width, height, fps)
                    for width, height in RECORDING_RESOLUTIONS
                ]

        options = {
            "video": video_options,
            "audio": audio_options,
            "address": stream_address,
            "srtp": True,
            "stream_count": config[CONF_STREAM_COUNT],
            "recording": self.secure_video,
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

        self._char_motion_detected = None
        self._recording_transport_start: asyncio.Task[None] | None = None
        self._recording_transport_stop: asyncio.Task[None] | None = None
        self._recording_with_audio = False
        self._cancel_motion_reset: CALLBACK_TYPE | None = None
        self.linked_motion_sensor: str | None = self.config.get(
            CONF_LINKED_MOTION_SENSOR
        )
        self.motion_is_event = False
        if linked_motion_sensor := self.linked_motion_sensor:
            self.motion_is_event = linked_motion_sensor.startswith("event.")
            state = self.hass.states.get(linked_motion_sensor)
            if self.secure_video:
                # Recordings are triggered by the motion sensor pyhap links.
                self._char_motion_detected = self.get_service(
                    SERV_MOTION_SENSOR
                ).get_characteristic(CHAR_MOTION_DETECTED)
            elif state:
                serv_motion = self.add_preload_service(SERV_MOTION_SENSOR)
                self._char_motion_detected = serv_motion.configure_char(
                    CHAR_MOTION_DETECTED, value=False
                )
            if state:
                self._async_update_motion_state(None, state)

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
        if self.secure_video:
            self._recording_transport_start = self._async_create_entry_task(
                self._async_start_recording_transport(),
                f"homekit.camera-recording-transport-{self.entity_id}",
            )

        super().run()

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
                "%s: Set linked motion %s sensor to True",
                self.entity_id,
                self.linked_motion_sensor,
            )
            char.set_value(True)
            if self._cancel_motion_reset:
                self._cancel_motion_reset()
            self._cancel_motion_reset = async_call_later(
                self.hass, MOTION_EVENT_RESET_SECONDS, self._async_reset_motion
            )
            return

        detected = state == STATE_ON
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
    def _async_reset_motion(self, _now: datetime) -> None:
        """Reset the motion detected characteristic after a motion event."""
        self._cancel_motion_reset = None
        if TYPE_CHECKING:
            assert self._char_motion_detected is not None
        self._char_motion_detected.set_value(False)

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

    async def start_stream(
        self, session_info: dict[str, Any], stream_config: dict[str, Any]
    ) -> bool:
        """Start a new stream with the given configuration."""
        _LOGGER.debug(
            "[%s] Starting stream with the following parameters: %s",
            session_info["id"],
            stream_config,
        )
        if not self.homekit_camera_active:
            _LOGGER.debug("[%s] Camera is off in the Home app", self.entity_id)
            return False
        if not (input_source := await self._async_get_stream_source()):
            _LOGGER.error("Camera has no stream source")
            return False
        input_source = with_input_flag(input_source)
        video_profile = ""
        if self.config[CONF_VIDEO_CODEC] != VIDEO_CODEC_COPY:
            video_profile = (
                "-profile:v "
                + self.config[CONF_VIDEO_PROFILE_NAMES][
                    int.from_bytes(stream_config["v_profile_id"], byteorder="big")
                ]
                + " "
            )
        audio_application = ""
        audio_frame_duration = ""
        if self.config[CONF_AUDIO_CODEC] == "libopus":
            audio_application = "-application lowdelay "
            audio_frame_duration = (
                f"-frame_duration {stream_config.get('a_packet_time', 20)} "
            )
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
                "v_profile": video_profile,
                "v_bufsize": stream_config["v_max_bitrate"] * 4,
                "v_map": self.config[CONF_VIDEO_MAP],
                "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
                "v_codec": self.config[CONF_VIDEO_CODEC],
                "a_bufsize": stream_config["a_max_bitrate"] * 4,
                "a_map": self.config[CONF_AUDIO_MAP],
                "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
                "a_encoder": self.config[CONF_AUDIO_CODEC],
                "a_application": audio_application,
                "a_frame_duration": audio_frame_duration,
                "a_proxy_port": audio_proxy.local_port if audio_proxy else 0,
            }
        )
        output = VIDEO_OUTPUT.format(**output_vars)
        if self.config[CONF_SUPPORT_AUDIO]:
            output = output + " " + AUDIO_OUTPUT.format(**output_vars)
        _LOGGER.debug("FFmpeg output settings: %s", output)
        stream = HAFFmpeg(self._ffmpeg.binary)
        opened = await stream.open(
            cmd=[],
            input_source=input_source,
            output=output,
            extra_cmd="-hide_banner -nostats",
            stderr_pipe=True,
            stdout_pipe=False,
        )
        if not opened:
            _LOGGER.error("Failed to open ffmpeg stream")
            if audio_proxy:
                await audio_proxy.async_stop()
            return False

        _LOGGER.debug(
            "[%s] Started stream process - PID %d",
            session_info["id"],
            stream.process.pid,
        )

        session_info["stream"] = stream
        session_info[FFMPEG_PID] = stream.process.pid
        session_info[AUDIO_PROXY] = audio_proxy

        stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)

        async def watch_session(_: Any) -> None:
            await self._async_ffmpeg_watch(session_info["id"])

        session_info[FFMPEG_LOGGER] = create_eager_task(
            self._async_log_stderr_stream(stderr_reader)
        )
        session_info[FFMPEG_WATCHER] = async_track_time_interval(
            self.hass,
            watch_session,
            FFMPEG_WATCH_INTERVAL,
        )

        if not self.homekit_camera_active:
            # The camera was turned off while the stream started.
            await self.stop_stream(session_info)
            return False
        return await self._async_ffmpeg_watch(session_info["id"])

    async def _async_log_stderr_stream(
        self, stderr_reader: asyncio.StreamReader
    ) -> None:
        """Log output from ffmpeg."""
        _LOGGER.debug("%s: ffmpeg: started", self.display_name)
        while True:
            line = await stderr_reader.readline()
            if line == b"":
                return

            _LOGGER.debug("%s: ffmpeg: %s", self.display_name, line.rstrip())

    async def _async_ffmpeg_watch(self, session_id: str) -> bool:
        """Check to make sure ffmpeg is still running and cleanup if not."""
        ffmpeg_pid = self.sessions[session_id][FFMPEG_PID]
        if pid_is_alive(ffmpeg_pid):
            return True

        _LOGGER.warning("Streaming process ended unexpectedly - PID %d", ffmpeg_pid)
        self._async_stop_ffmpeg_watch(session_id)
        self.set_streaming_available(self.sessions[session_id]["stream_idx"])
        return False

    @callback
    def _async_stop_ffmpeg_watch(self, session_id: str) -> None:
        """Cleanup a streaming session after stopping."""
        if FFMPEG_WATCHER not in self.sessions[session_id]:
            return
        self.sessions[session_id].pop(FFMPEG_WATCHER)()
        self.sessions[session_id].pop(FFMPEG_LOGGER).cancel()

    @callback
    @override
    def async_stop(self) -> None:
        """Stop any streams when the accessory is stopped."""
        if self._cancel_motion_reset:
            self._cancel_motion_reset()
            self._cancel_motion_reset = None
        for session_info in self.sessions.values():
            self.hass.async_create_background_task(
                self.stop_stream(session_info), "homekit.camera-stop-stream"
            )
        if self.secure_video:
            self._recording_transport_stop = self._async_create_entry_task(
                self._async_stop_recording_transport(),
                f"homekit.camera-stop-recording-transport-{self.entity_id}",
            )
        super().async_stop()

    @override
    async def stop(self) -> None:
        """Stop the accessory and wait for the recording transport to close."""
        await super().stop()
        if self._recording_transport_stop:
            await self._recording_transport_stop

    async def _async_stop_recording_transport(self) -> None:
        """Close the recording listener once it has started."""
        # Wait for a pending start so the listener is closed when stop() returns.
        if self._recording_transport_start:
            await asyncio.wait({self._recording_transport_start})
        await self.stop_recording_transport()

    async def _async_start_recording_transport(self) -> None:
        """Start the HomeKit Data Stream listener recordings are sent over."""
        try:
            await self.start_recording_transport()
        except OSError as err:
            _LOGGER.error(
                "[%s] HomeKit Secure Video cannot listen for recordings: %s",
                self.entity_id,
                err,
            )

    @override
    def _default_recording_configs(
        self, options: dict[str, Any]
    ) -> tuple[
        SupportedRecordingConfiguration,
        list[VideoCodecConfiguration],
        list[AudioCodecConfiguration],
    ]:
        """Advertise only recording formats a home hub can select."""
        general, video, audio = super()._default_recording_configs(options)
        # No prebuffer is kept, the recording starts when the hub asks for it.
        general.prebuffer_length_ms = 0
        video[0].attributes = self._recording_attributes
        return general, video, audio

    @override
    def diagnostics(self) -> dict[str, Any]:
        """Return the HomeKit Secure Video state for diagnostics."""
        if not self.secure_video:
            return {}
        selected = self.selected_recording_configuration
        return {
            "secure_video": {
                "active": self.recording_active,
                "audio_active": self.recording_audio_active,
                "homekit_camera_active": self.homekit_camera_active,
                "selected_configuration": asdict(selected) if selected else None,
                "transport_port": self.recording_transport_port,
                "connections": self.recording_connection_count,
            }
        }

    def _log_recording_problem(self, message: str, *args: Any) -> None:
        """Warn about each kind of recording failure once until one succeeds."""
        level = logging.DEBUG if message == self._recording_problem else logging.WARNING
        self._recording_problem = message
        _LOGGER.log(level, message, self.entity_id, *args)

    @callback
    def _async_create_entry_task[_R](
        self, target: Coroutine[Any, Any, _R], name: str
    ) -> asyncio.Task[_R]:
        """Run a background task that ends with the HomeKit config entry."""
        entry = self.hass.config_entries.async_get_known_entry(self.driver.entry_id)
        return entry.async_create_background_task(self.hass, target, name)

    @override
    def homekit_camera_active_changed(self, active: bool) -> None:
        """Stop live streams when the camera is turned off in the Home app."""
        if active:
            return
        # A starting stream checks the camera state once ffmpeg runs.
        # The eager end tasks may change the sessions while we iterate.
        for session_info in list(self.sessions.values()):
            if "stream" in session_info:
                self._async_create_entry_task(
                    self._async_end_session(session_info),
                    f"homekit.camera-end-session-{self.entity_id}",
                )

    async def _async_end_session(self, session_info: dict[str, Any]) -> None:
        """End a live stream, the controller removes the session with its stop."""
        await self.stop_stream(session_info)
        self._close_talkback(session_info)
        # The controller may have started a new session on this slot meanwhile.
        if self.sessions.get(session_info["id"]) is session_info:
            self.set_streaming_available(session_info["stream_idx"])

    @override
    def recording_state_changed(self) -> None:
        """End a running recording the hub no longer allows as it is."""
        recording = self._recording_stream
        if recording is None or not recording.streaming:
            return
        if (
            not self.recording_active
            or self.recording_audio_active != self._recording_with_audio
        ):
            recording.close(RecordingReason.NOT_ALLOWED)

    @override
    async def handle_recording_stream(
        self, stream_id: int
    ) -> AsyncGenerator[RecordingPacket]:
        """Stream a HomeKit Secure Video recording from ffmpeg."""
        self._recording_with_audio = self.recording_audio_active
        if not (input_source := await self._async_get_stream_source()):
            self._log_recording_problem("[%s] Camera has no stream source")
            return
        selected = self.selected_recording_configuration
        if TYPE_CHECKING:
            assert isinstance(selected, SelectedRecordingConfiguration)
        try:
            input_args, output = recording_ffmpeg_args(
                self.config, selected, input_source, self._recording_with_audio
            )
        except (ValueError, LookupError) as err:
            # A stream source shlex cannot split or a format we did not advertise.
            self._log_recording_problem("[%s] Cannot build the recording: %s", err)
            return
        _LOGGER.debug("[%s] Recording %s with: %s", self.entity_id, stream_id, output)
        stream = HAFFmpeg(self._ffmpeg.binary)
        if not await stream.open(
            cmd=[],
            input_source=input_args,
            output=output,
            extra_cmd="-hide_banner -nostats -loglevel error",
            stdout_pipe=True,
            stderr_pipe=True,
        ):
            self._log_recording_problem("[%s] Failed to start recording ffmpeg")
            return
        stderr: deque[str] = deque(maxlen=RECORDING_STDERR_LINES)
        stderr_task = self._async_create_entry_task(
            self._async_collect_stderr(await stream.get_reader(FFMPEG_STDERR), stderr),
            f"homekit.camera-recording-stderr-{self.entity_id}",
        )
        packets = fmp4_recording_packets(await stream.get_reader())
        sent_packets = 0
        try:
            while True:
                try:
                    async with asyncio.timeout(RECORDING_TIMEOUT):
                        packet = await anext(packets, None)
                except TimeoutError:
                    self._log_recording_problem(
                        "[%s] Recording ended, ffmpeg delivered no video for %s"
                        " seconds: %s",
                        RECORDING_TIMEOUT,
                        " ".join(stderr),
                    )
                    return
                if packet is None or packet.is_last:
                    if await self._async_recording_failed(stream, stderr_task, stderr):
                        return
                    if packet is None or sent_packets < RECORDING_FIRST_VIDEO_PACKET:
                        self._log_recording_problem(
                            "[%s] Recording ffmpeg ended without video: %s",
                            " ".join(stderr),
                        )
                        return
                sent_packets += 1
                if sent_packets == RECORDING_FIRST_VIDEO_PACKET:
                    self._recording_problem = None
                yield packet
                if packet.is_last:
                    return
        finally:
            await packets.aclose()
            # kill() reads stderr itself, so our reader must stop first.
            stderr_task.cancel()
            await asyncio.wait({stderr_task})
            # Closing would wait for ffmpeg to flush, the hub already ended.
            if stream.is_running:
                stream.kill()
                await stream.process.wait()

    async def _async_recording_failed(
        self,
        stream: HAFFmpeg,
        stderr_task: asyncio.Task[None],
        stderr: deque[str],
    ) -> bool:
        """Log and return if the recording ffmpeg exited with an error."""
        try:
            async with asyncio.timeout(RECORDING_EXIT_TIMEOUT):
                returncode = await stream.process.wait()
        except TimeoutError:
            self._log_recording_problem(
                "[%s] Recording ffmpeg did not exit after its output ended"
            )
            return True
        # Both a failure and a recording without video report the last lines.
        await asyncio.wait({stderr_task}, timeout=RECORDING_STDERR_DRAIN_SECONDS)
        if not returncode:
            return False
        self._log_recording_problem(
            "[%s] Recording ffmpeg exited with %s: %s",
            returncode,
            " ".join(stderr),
        )
        return True

    async def _async_collect_stderr(
        self, reader: asyncio.StreamReader, lines: deque[str]
    ) -> None:
        """Keep the last ffmpeg output lines of a recording."""
        skip_line = False
        while True:
            try:
                raw = await reader.readuntil(b"\n")
            except asyncio.IncompleteReadError as err:
                raw = err.partial
            except asyncio.LimitOverrunError as err:
                # Drop the part over the limit and skip the rest of its line, where
                # a URL would no longer match the redaction.
                await reader.readexactly(err.consumed)
                lines.append("<line too long>")
                skip_line = True
                continue
            if not raw:
                return
            if skip_line:
                skip_line = False
                continue
            line = RECORDING_STDERR_URL.sub(b"<url>", raw.rstrip()).decode(
                errors="replace"
            )
            _LOGGER.debug("[%s] Recording ffmpeg: %s", self.entity_id, line)
            lines.append(line)

    async def stop_stream(self, session_info: dict[str, Any]) -> None:
        """Stop the stream for the given ``session_id``."""
        session_id = session_info["id"]
        if proxy := session_info.pop(AUDIO_PROXY, None):
            await proxy.async_stop()

        # Taken out before awaiting the close so a concurrent stop skips it.
        if not (stream := session_info.pop("stream", None)):
            _LOGGER.debug("No stream for session ID %s", session_id)
            return

        self._async_stop_ffmpeg_watch(session_id)

        if not pid_is_alive(stream.process.pid):
            _LOGGER.warning("[%s] Stream already stopped", session_id)
            return

        for shutdown_method in ("close", "kill"):
            _LOGGER.debug("[%s] %s stream", session_id, shutdown_method)
            try:
                await getattr(stream, shutdown_method)()
            except Exception:
                _LOGGER.exception(
                    "[%s] Failed to %s stream", session_id, shutdown_method
                )
            else:
                return

    async def reconfigure_stream(
        self, session_info: dict[str, Any], stream_config: dict[str, Any]
    ) -> bool:
        """Reconfigure the stream so that it uses the given ``stream_config``."""
        # A camera turned off has no stream left to reconfigure.
        return bool(self.homekit_camera_active)

    def _raise_if_camera_off(self) -> None:
        if not self.homekit_camera_active:
            raise HomeAssistantError("Camera is off in the Home app")

    async def async_get_snapshot(self, image_size: dict[str, int]) -> bytes:
        """Return a jpeg of a snapshot from the camera."""
        self._raise_if_camera_off()
        image = await camera.async_get_image(
            self.hass,
            self.entity_id,
            width=image_size["image-width"],
            height=image_size["image-height"],
        )
        self._raise_if_camera_off()
        return image.content
