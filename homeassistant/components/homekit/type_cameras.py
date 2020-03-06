"""Class to hold all camera accessories."""
import asyncio
import ipaddress
import logging
import os
import struct
from uuid import UUID

from haffmpeg.core import HAFFmpeg
from pyhap import tlv
from pyhap.camera import (
    AUDIO_CODEC_TYPES,
    NO_SRTP,
    SETUP_ADDR_INFO,
    SETUP_SRTP_PARAM,
    SETUP_STATUS,
    SETUP_TYPES,
    SRTP_CRYPTO_SUITES,
    STREAMING_STATUS,
    VIDEO_CODEC_PARAM_LEVEL_TYPES,
    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES,
    Camera as PyhapCamera,
)
from pyhap.const import CATEGORY_CAMERA
from pyhap.util import to_base64_str

from homeassistant.components.camera.const import DOMAIN as DOMAIN_CAMERA
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.util import get_local_ip

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_SELECTED_RTP_STREAM_CONFIGURATION,
    CHAR_SETUP_ENDPOINTS,
    CHAR_STREAMING_STATUS,
    CHAR_SUPPORTED_AUDIO_STREAM_CONFIGURATION,
    CHAR_SUPPORTED_RTP_CONFIGURATION,
    CHAR_SUPPORTED_VIDEO_STREAM_CONFIGURATION,
    CONF_AUDIO_MAP,
    CONF_AUDIO_PACKET_SIZE,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
    CONF_STREAM_ADDRESS,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_MAP,
    CONF_VIDEO_PACKET_SIZE,
    SERV_CAMERA_RTP_STREAM_MANAGEMENT,
    SERV_MICROPHONE,
)
from .util import CAMERA_SCHEMA

_LOGGER = logging.getLogger(__name__)

VIDEO_OUTPUT = (
    "-map {v_map} -an "
    "-c:v libx264 -profile:v {v_profile} -tune zerolatency -pix_fmt yuv420p "
    "-r {fps} "
    "-vf 'scale=min({width}\\,iw):min({height}\\,ih):force_original_aspect_ratio=increase' "
    "-b:v {v_max_bitrate}k -bufsize {v_bufsize}k -maxrate {v_max_bitrate}k "
    "-payload_type 99 "
    "-ssrc {v_ssrc} -f rtp "
    "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params {v_srtp_key} "
    "srtp://{address}:{v_port}?rtcpport={v_port}&"
    "localrtcpport={v_port}&pkt_size={v_pkt_size}"
)

AUDIO_ENCODER_OPUS = "libopus -application lowdelay"

AUDIO_ENCODER_AAC = "libfdk_aac -profile:a aac_eld -flags +global_header"

AUDIO_OUTPUT = (
    "-map {a_map} -vn "
    "-c:a {a_encoder} "
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
]

VIDEO_PROFILE_NAMES = ["baseline", "main", "high"]


@TYPES.register("Camera")
class Camera(HomeAccessory):
    """Generate a Camera accessory."""

    def __init__(self, *args):
        """Initialize a Camera accessory object."""
        super().__init__(*args, category=CATEGORY_CAMERA)
        self._ffmpeg = self.hass.data[DATA_FFMPEG]
        self._camera = self.hass.data[DOMAIN_CAMERA]

        self.config = CAMERA_SCHEMA(self.config)

        max_fps = self.config[CONF_MAX_FPS]
        max_width = self.config[CONF_MAX_WIDTH]
        max_height = self.config[CONF_MAX_HEIGHT]
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
                {"type": "AAC-eld", "samplerate": 16},
            ]
        }

        self.streaming_status = STREAMING_STATUS["AVAILABLE"]
        self.has_srtp = True
        self.stream_address = self.config.get(CONF_STREAM_ADDRESS) or get_local_ip()
        try:
            ipaddress.IPv4Address(self.stream_address)
            self.stream_address_isv6 = b"\x00"
        except ValueError:
            self.stream_address_isv6 = b"\x01"
        self.sessions = {}

        if self.config[CONF_SUPPORT_AUDIO]:
            self.add_preload_service(SERV_MICROPHONE)
        management = self.add_preload_service(SERV_CAMERA_RTP_STREAM_MANAGEMENT)
        management.configure_char(
            CHAR_STREAMING_STATUS, getter_callback=self._get_streaming_status
        )
        management.configure_char(
            CHAR_SUPPORTED_RTP_CONFIGURATION,
            value=PyhapCamera.get_supported_rtp_config(True),
        )
        management.configure_char(
            CHAR_SUPPORTED_VIDEO_STREAM_CONFIGURATION,
            value=PyhapCamera.get_supported_video_stream_config(video_options),
        )
        management.configure_char(
            CHAR_SUPPORTED_AUDIO_STREAM_CONFIGURATION,
            value=PyhapCamera.get_supported_audio_stream_config(audio_options),
        )
        management.configure_char(
            CHAR_SELECTED_RTP_STREAM_CONFIGURATION,
            setter_callback=self.set_selected_stream_configuration,
        )
        management.configure_char(
            CHAR_SETUP_ENDPOINTS, setter_callback=self.set_endpoints
        )

    def update_state(self, new_state):
        """Handle state change to update HomeKit value."""
        pass

    def _get_streaming_status(self):
        return PyhapCamera._get_streaimg_status(self)

    async def _start_stream(self, objs, reconfigure):
        return await PyhapCamera._start_stream(self, objs, reconfigure)

    async def _stop_stream(self, objs):
        return await PyhapCamera._stop_stream(self, objs)

    def set_selected_stream_configuration(self, value):
        """Set the selected stream configuration."""
        return PyhapCamera.set_selected_stream_configuration(self, value)

    def set_endpoints(self, value):
        """Configure streaming endpoints."""
        objs = tlv.decode(value, from_base64=True)
        session_id = UUID(bytes=objs[SETUP_TYPES["SESSION_ID"]])

        # Extract address info
        address_tlv = objs[SETUP_TYPES["ADDRESS"]]
        address_info_objs = tlv.decode(address_tlv)
        is_ipv6 = struct.unpack("?", address_info_objs[SETUP_ADDR_INFO["ADDRESS_VER"]])[
            0
        ]
        address = address_info_objs[SETUP_ADDR_INFO["ADDRESS"]].decode("utf8")
        target_video_port = struct.unpack(
            "<H", address_info_objs[SETUP_ADDR_INFO["VIDEO_RTP_PORT"]]
        )[0]
        target_audio_port = struct.unpack(
            "<H", address_info_objs[SETUP_ADDR_INFO["AUDIO_RTP_PORT"]]
        )[0]

        # Video SRTP Params
        video_srtp_tlv = objs[SETUP_TYPES["VIDEO_SRTP_PARAM"]]
        video_info_objs = tlv.decode(video_srtp_tlv)
        video_crypto_suite = video_info_objs[SETUP_SRTP_PARAM["CRYPTO"]][0]
        video_master_key = video_info_objs[SETUP_SRTP_PARAM["MASTER_KEY"]]
        video_master_salt = video_info_objs[SETUP_SRTP_PARAM["MASTER_SALT"]]

        # Audio SRTP Params
        audio_srtp_tlv = objs[SETUP_TYPES["AUDIO_SRTP_PARAM"]]
        audio_info_objs = tlv.decode(audio_srtp_tlv)
        audio_crypto_suite = audio_info_objs[SETUP_SRTP_PARAM["CRYPTO"]][0]
        audio_master_key = audio_info_objs[SETUP_SRTP_PARAM["MASTER_KEY"]]
        audio_master_salt = audio_info_objs[SETUP_SRTP_PARAM["MASTER_SALT"]]

        _LOGGER.debug(
            "Received endpoint configuration:"
            "\nsession_id: %s\naddress: %s\nis_ipv6: %s"
            "\ntarget_video_port: %s\ntarget_audio_port: %s"
            "\nvideo_crypto_suite: %s\nvideo_srtp: %s"
            "\naudio_crypto_suite: %s\naudio_srtp: %s",
            session_id,
            address,
            is_ipv6,
            target_video_port,
            target_audio_port,
            video_crypto_suite,
            to_base64_str(video_master_key + video_master_salt),
            audio_crypto_suite,
            to_base64_str(audio_master_key + audio_master_salt),
        )

        # Configure the SetupEndpoints response

        if self.has_srtp:
            video_srtp_tlv = tlv.encode(
                SETUP_SRTP_PARAM["CRYPTO"],
                SRTP_CRYPTO_SUITES["AES_CM_128_HMAC_SHA1_80"],
                SETUP_SRTP_PARAM["MASTER_KEY"],
                video_master_key,
                SETUP_SRTP_PARAM["MASTER_SALT"],
                video_master_salt,
            )

            audio_srtp_tlv = tlv.encode(
                SETUP_SRTP_PARAM["CRYPTO"],
                SRTP_CRYPTO_SUITES["AES_CM_128_HMAC_SHA1_80"],
                SETUP_SRTP_PARAM["MASTER_KEY"],
                audio_master_key,
                SETUP_SRTP_PARAM["MASTER_SALT"],
                audio_master_salt,
            )
        else:
            video_srtp_tlv = NO_SRTP
            audio_srtp_tlv = NO_SRTP

        video_ssrc = int.from_bytes(os.urandom(3), byteorder="big")
        audio_ssrc = int.from_bytes(os.urandom(3), byteorder="big")

        res_address_tlv = tlv.encode(
            SETUP_ADDR_INFO["ADDRESS_VER"],
            self.stream_address_isv6,
            SETUP_ADDR_INFO["ADDRESS"],
            self.stream_address.encode("utf-8"),
            SETUP_ADDR_INFO["VIDEO_RTP_PORT"],
            struct.pack("<H", target_video_port),
            SETUP_ADDR_INFO["AUDIO_RTP_PORT"],
            struct.pack("<H", target_audio_port),
        )

        response_tlv = tlv.encode(
            SETUP_TYPES["SESSION_ID"],
            session_id.bytes,
            SETUP_TYPES["STATUS"],
            SETUP_STATUS["SUCCESS"],
            SETUP_TYPES["ADDRESS"],
            res_address_tlv,
            SETUP_TYPES["VIDEO_SRTP_PARAM"],
            video_srtp_tlv,
            SETUP_TYPES["AUDIO_SRTP_PARAM"],
            audio_srtp_tlv,
            SETUP_TYPES["VIDEO_SSRC"],
            struct.pack("<I", video_ssrc),
            SETUP_TYPES["AUDIO_SSRC"],
            struct.pack("<I", audio_ssrc),
            to_base64=True,
        )

        self.sessions[session_id] = {
            "id": session_id,
            "address": address,
            "v_port": target_video_port,
            "v_srtp_key": to_base64_str(video_master_key + video_master_salt),
            "v_ssrc": video_ssrc,
            "a_port": target_audio_port,
            "a_srtp_key": to_base64_str(audio_master_key + audio_master_salt),
            "a_ssrc": audio_ssrc,
        }

        self.get_service(SERV_CAMERA_RTP_STREAM_MANAGEMENT).get_characteristic(
            CHAR_SETUP_ENDPOINTS
        ).set_value(response_tlv)

    async def stop(self):
        """Stop all streaming sessions."""
        return await PyhapCamera.stop(self)

    def _get_stream_source(self):
        camera = self._camera.get_entity(self.entity_id)
        if not camera or not camera.is_on:
            return None
        stream_source = self.config.get(CONF_STREAM_SOURCE)
        if stream_source:
            return stream_source
        try:
            stream_source = asyncio.run_coroutine_threadsafe(
                camera.stream_source(), self.hass.loop
            ).result(10)
        except Exception as err:
            _LOGGER.error("Failed to get stream source: %s", err)
        return stream_source

    async def start_stream(self, session_info, stream_config):
        """Start a new stream with the given configuration."""
        _LOGGER.debug(
            "[%s] Starting stream with the following parameters: %s",
            session_info["id"],
            stream_config,
        )

        input_source = self._get_stream_source()
        if not input_source:
            _LOGGER.error("Camera has no stream source")
            return False

        if "-i " not in input_source:
            input_source = "-i " + input_source

        output_vars = stream_config.copy()
        output_vars.update(
            {
                "v_profile": VIDEO_PROFILE_NAMES[
                    int.from_bytes(stream_config["v_profile_id"], byteorder="big")
                ],
                "v_bufsize": stream_config["v_max_bitrate"] * 2,
                "v_map": self.config[CONF_VIDEO_MAP],
                "v_pkt_size": self.config[CONF_VIDEO_PACKET_SIZE],
                "a_bufsize": stream_config["a_max_bitrate"] * 2,
                "a_map": self.config[CONF_AUDIO_MAP],
                "a_pkt_size": self.config[CONF_AUDIO_PACKET_SIZE],
                "a_encoder": (
                    AUDIO_ENCODER_OPUS
                    if stream_config["a_codec"] == AUDIO_CODEC_TYPES["OPUS"]
                    else AUDIO_ENCODER_AAC
                ),
            }
        )
        output = VIDEO_OUTPUT.format(**output_vars)
        if self.config[CONF_SUPPORT_AUDIO]:
            output = output + " " + AUDIO_OUTPUT.format(**output_vars)

        stream = HAFFmpeg(self._ffmpeg.binary, loop=self.driver.loop)
        opened = await stream.open(
            cmd=[], input_source=input_source, output=output, stdout_pipe=False
        )
        if not opened:
            _LOGGER.error("Failed to open ffmpeg stream")
            return False

        session_info["stream"] = stream
        _LOGGER.info(
            "[%s] Started stream process - PID %d",
            session_info["id"],
            stream.process.pid,
        )
        return True

    async def stop_stream(self, session_info):
        """Stop the stream for the given ``session_id``."""
        session_id = session_info["id"]
        stream = session_info.get("stream")
        if stream:
            _LOGGER.info("[%s] Stopping stream.", session_id)
            await stream.close()
            _LOGGER.debug("Stream process stopped.")
        else:
            _LOGGER.warning("No stream for session ID %s", session_id)

    async def reconfigure_stream(self, session_info, stream_config):
        """Reconfigure the stream so that it uses the given ``stream_config``."""
        return True

    def get_snapshot(self, image_size):
        """Return an ``Image`` of a snapshot from the camera."""
        return asyncio.run_coroutine_threadsafe(
            self.hass.components.camera.async_get_image(self.entity_id), self.hass.loop
        ).result()
