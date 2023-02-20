"""Class to hold all camera accessories."""
import asyncio
from datetime import timedelta
import logging

from haffmpeg.core import FFMPEG_STDERR, HAFFmpeg
from pyhap.camera import (
    VIDEO_CODEC_PARAM_LEVEL_TYPES,
    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES,
    Camera as PyhapCamera,
)
from pyhap.const import CATEGORY_CAMERA

from homeassistant.components import camera
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.const import STATE_ON
from homeassistant.core import Event, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_MOTION_DETECTED,
    CHAR_MUTE,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    CONF_AUDIO_CODEC,
    CONF_AUDIO_MAP,
    CONF_AUDIO_PACKET_SIZE,
    CONF_LINKED_DOORBELL_SENSOR,
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
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_MAP,
    DEFAULT_AUDIO_PACKET_SIZE,
    DEFAULT_MAX_FPS,
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_STREAM_COUNT,
    DEFAULT_SUPPORT_AUDIO,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_MAP,
    DEFAULT_VIDEO_PACKET_SIZE,
    SERV_DOORBELL,
    SERV_MOTION_SENSOR,
    SERV_SPEAKER,
    SERV_STATELESS_PROGRAMMABLE_SWITCH,
)
from .util import pid_is_alive, state_changed_event_is_same_state

_LOGGER = logging.getLogger(__name__)

DOORBELL_SINGLE_PRESS = 0
DOORBELL_DOUBLE_PRESS = 1
DOORBELL_LONG_PRESS = 2

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
    "localrtcpport={v_port}&pkt_size={v_pkt_size}"
)

AUDIO_OUTPUT = (
    "-map {a_map} -vn "
    "-c:a {a_encoder} "
    "{a_application}"
    "-ac 1 -ar {a_sample_rate}k "
    "-b:a {a_max_bitrate}k -bufsize {a_bufsize}k "
    "-payload_type 110 "
    "-ssrc {a_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {a_srtp_key} "
    "srtp://{address}:{a_port}?rtcpport={a_port}&"
    "localrtcpport={a_port}&pkt_size={a_pkt_size}"
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

VIDEO_PROFILE_NAMES = ["baseline", "main", "high"]

FFMPEG_WATCH_INTERVAL = timedelta(seconds=5)
FFMPEG_LOGGER = "ffmpeg_logger"
FFMPEG_WATCHER = "ffmpeg_watcher"
FFMPEG_PID = "ffmpeg_pid"
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
    CONF_AUDIO_PACKET_SIZE: DEFAULT_AUDIO_PACKET_SIZE,
    CONF_VIDEO_PACKET_SIZE: DEFAULT_VIDEO_PACKET_SIZE,
    CONF_STREAM_COUNT: DEFAULT_STREAM_COUNT,
}


@TYPES.register("Camera")
class Camera(HomeAccessory, PyhapCamera):
    """Generate a Camera accessory."""

    def __init__(self, hass, driver, name, entity_id, aid, config):
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

        self._char_motion_detected = None
        self.linked_motion_sensor = self.config.get(CONF_LINKED_MOTION_SENSOR)
        if self.linked_motion_sensor:
            state = self.hass.states.get(self.linked_motion_sensor)
            if state:
                serv_motion = self.add_preload_service(SERV_MOTION_SENSOR)
                self._char_motion_detected = serv_motion.configure_char(
                    CHAR_MOTION_DETECTED, value=False
                )
                self._async_update_motion_state(state)

        self._char_doorbell_detected = None
        self._char_doorbell_detected_switch = None
        self.linked_doorbell_sensor = self.config.get(CONF_LINKED_DOORBELL_SENSOR)
        if self.linked_doorbell_sensor:
            state = self.hass.states.get(self.linked_doorbell_sensor)
            if state:
                serv_doorbell = self.add_preload_service(SERV_DOORBELL)
                self.set_primary_service(serv_doorbell)
                self._char_doorbell_detected = serv_doorbell.configure_char(
                    CHAR_PROGRAMMABLE_SWITCH_EVENT,
                    value=0,
                )
                serv_stateless_switch = self.add_preload_service(
                    SERV_STATELESS_PROGRAMMABLE_SWITCH
                )
                self._char_doorbell_detected_switch = (
                    serv_stateless_switch.configure_char(
                        CHAR_PROGRAMMABLE_SWITCH_EVENT,
                        value=0,
                        valid_values={"SinglePress": DOORBELL_SINGLE_PRESS},
                    )
                )
                serv_speaker = self.add_preload_service(SERV_SPEAKER)
                serv_speaker.configure_char(CHAR_MUTE, value=0)

                self._async_update_doorbell_state(state)

    async def run(self):
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        if self._char_motion_detected:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_motion_sensor],
                    self._async_update_motion_state_event,
                )
            )

        if self._char_doorbell_detected:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_doorbell_sensor],
                    self._async_update_doorbell_state_event,
                )
            )

        await super().run()

    @callback
    def _async_update_motion_state_event(self, event: Event) -> None:
        """Handle state change event listener callback."""
        if not state_changed_event_is_same_state(event):
            self._async_update_motion_state(event.data.get("new_state"))

    @callback
    def _async_update_motion_state(self, new_state):
        """Handle link motion sensor state change to update HomeKit value."""
        if not new_state:
            return

        detected = new_state.state == STATE_ON
        if self._char_motion_detected.value == detected:
            return

        self._char_motion_detected.set_value(detected)
        _LOGGER.debug(
            "%s: Set linked motion %s sensor to %d",
            self.entity_id,
            self.linked_motion_sensor,
            detected,
        )

    @callback
    def _async_update_doorbell_state_event(self, event: Event) -> None:
        """Handle state change event listener callback."""
        if not state_changed_event_is_same_state(event):
            self._async_update_doorbell_state(event.data.get("new_state"))

    @callback
    def _async_update_doorbell_state(self, new_state):
        """Handle link doorbell sensor state change to update HomeKit value."""
        if not new_state:
            return

        if new_state.state == STATE_ON:
            self._char_doorbell_detected.set_value(DOORBELL_SINGLE_PRESS)
            self._char_doorbell_detected_switch.set_value(DOORBELL_SINGLE_PRESS)
            _LOGGER.debug(
                "%s: Set linked doorbell %s sensor to %d",
                self.entity_id,
                self.linked_doorbell_sensor,
                DOORBELL_SINGLE_PRESS,
            )

    @callback
    def async_update_state(self, new_state):
        """Handle state change to update HomeKit value."""
        pass  # pylint: disable=unnecessary-pass

    async def _async_get_stream_source(self):
        """Find the camera stream source url."""
        if stream_source := self.config.get(CONF_STREAM_SOURCE):
            return stream_source
        try:
            stream_source = await camera.async_get_stream_source(
                self.hass, self.entity_id
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Failed to get stream source - this could be a transient error or your"
                " camera might not be compatible with HomeKit yet"
            )
        return stream_source

    async def start_stream(self, session_info, stream_config):
        """Start a new stream with the given configuration."""
        _LOGGER.debug(
            "[%s] Starting stream with the following parameters: %s",
            session_info["id"],
            stream_config,
        )
        if not (input_source := await self._async_get_stream_source()):
            _LOGGER.error("Camera has no stream source")
            return False
        if "-i " not in input_source:
            input_source = "-i " + input_source
        video_profile = ""
        if self.config[CONF_VIDEO_CODEC] != "copy":
            video_profile = (
                "-profile:v "
                + VIDEO_PROFILE_NAMES[
                    int.from_bytes(stream_config["v_profile_id"], byteorder="big")
                ]
                + " "
            )
        audio_application = ""
        if self.config[CONF_AUDIO_CODEC] == "libopus":
            audio_application = "-application lowdelay "
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
            return False

        _LOGGER.info(
            "[%s] Started stream process - PID %d",
            session_info["id"],
            stream.process.pid,
        )

        session_info["stream"] = stream
        session_info[FFMPEG_PID] = stream.process.pid

        stderr_reader = await stream.get_reader(source=FFMPEG_STDERR)

        async def watch_session(_):
            await self._async_ffmpeg_watch(session_info["id"])

        session_info[FFMPEG_LOGGER] = asyncio.create_task(
            self._async_log_stderr_stream(stderr_reader)
        )
        session_info[FFMPEG_WATCHER] = async_track_time_interval(
            self.hass,
            watch_session,
            FFMPEG_WATCH_INTERVAL,
        )

        return await self._async_ffmpeg_watch(session_info["id"])

    async def _async_log_stderr_stream(self, stderr_reader):
        """Log output from ffmpeg."""
        _LOGGER.debug("%s: ffmpeg: started", self.display_name)
        while True:
            line = await stderr_reader.readline()
            if line == b"":
                return

            _LOGGER.debug("%s: ffmpeg: %s", self.display_name, line.rstrip())

    async def _async_ffmpeg_watch(self, session_id):
        """Check to make sure ffmpeg is still running and cleanup if not."""
        ffmpeg_pid = self.sessions[session_id][FFMPEG_PID]
        if pid_is_alive(ffmpeg_pid):
            return True

        _LOGGER.warning("Streaming process ended unexpectedly - PID %d", ffmpeg_pid)
        self._async_stop_ffmpeg_watch(session_id)
        self.set_streaming_available(self.sessions[session_id]["stream_idx"])
        return False

    @callback
    def _async_stop_ffmpeg_watch(self, session_id):
        """Cleanup a streaming session after stopping."""
        if FFMPEG_WATCHER not in self.sessions[session_id]:
            return
        self.sessions[session_id].pop(FFMPEG_WATCHER)()
        self.sessions[session_id].pop(FFMPEG_LOGGER).cancel()

    async def stop(self):
        """Stop any streams when the accessory is stopped."""
        for session_info in self.sessions.values():
            self.hass.async_create_background_task(
                self.stop_stream(session_info), "homekit.camera-stop-stream"
            )
        await super().stop()

    async def stop_stream(self, session_info):
        """Stop the stream for the given ``session_id``."""
        session_id = session_info["id"]
        if not (stream := session_info.get("stream")):
            _LOGGER.debug("No stream for session ID %s", session_id)
            return

        self._async_stop_ffmpeg_watch(session_id)

        if not pid_is_alive(stream.process.pid):
            _LOGGER.info("[%s] Stream already stopped", session_id)
            return True

        for shutdown_method in ("close", "kill"):
            _LOGGER.info("[%s] %s stream", session_id, shutdown_method)
            try:
                await getattr(stream, shutdown_method)()
                return
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "[%s] Failed to %s stream", session_id, shutdown_method
                )

    async def reconfigure_stream(self, session_info, stream_config):
        """Reconfigure the stream so that it uses the given ``stream_config``."""
        return True

    async def async_get_snapshot(self, image_size):
        """Return a jpeg of a snapshot from the camera."""
        image = await camera.async_get_image(
            self.hass,
            self.entity_id,
            width=image_size["image-width"],
            height=image_size["image-height"],
        )
        return image.content
