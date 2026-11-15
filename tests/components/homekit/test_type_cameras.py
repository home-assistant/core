"""Test different accessory types: Camera."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import timedelta
import logging
import struct
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import UUID

from freezegun.api import FrozenDateTimeFactory
from pyhap import tlv
from pyhap.camera import (
    SELECTED_STREAM_CONFIGURATION_TYPES,
    SETUP_TYPES,
    STREAMING_STATUS,
)
from pyhap.const import STANDALONE_AID
from pyhap.hds_recording import RecordingPacket
from pyhap.hksv_recording import (
    AudioCodecConfiguration,
    AudioSampleRate,
    SelectedRecordingConfiguration,
    SupportedRecordingConfiguration,
    VideoAttributes,
    VideoCodecConfiguration,
    VideoCodecType,
    decode_supported_video,
)
from pyhap.util import base64_to_bytes, to_base64_str
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components import camera, ffmpeg
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.camera import TurboJPEGSingleton
from homeassistant.components.event import EventDeviceClass
from homeassistant.components.homekit.accessories import HomeBridge, HomeDriver
from homeassistant.components.homekit.const import (
    AUDIO_CODEC_COPY,
    CAMERA_MODE_SECURE_VIDEO,
    CAMERA_MODE_STANDARD,
    CHAR_MOTION_DETECTED,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    CONF_AUDIO_CODEC,
    CONF_CAMERA_MODE,
    CONF_LINKED_DOORBELL_SENSOR,
    CONF_LINKED_MOTION_SENSOR,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    CONF_VIDEO_PROFILE_NAMES,
    SERV_DOORBELL,
    SERV_MOTION_SENSOR,
    SERV_STATELESS_PROGRAMMABLE_SWITCH,
    VIDEO_CODEC_COPY,
    VIDEO_CODEC_H264_OMX,
    VIDEO_CODEC_H264_V4L2M2M,
)
from homeassistant.components.homekit.type_cameras import (
    CONFIG_DEFAULTS,
    MOTION_EVENT_RESET_SECONDS,
    Camera,
    recording_ffmpeg_args,
)
from homeassistant.components.homekit.type_switches import Switch
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.components.camera.common import mock_turbo_jpeg

MOCK_AUDIO_PROXY_PORT = 23456
MOCK_START_STREAM_TLV = (
    "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAg"
    "AFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAg"
    "EAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
)
MOCK_END_POINTS_TLV = (
    "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7"
    "IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4Cw"
    "UlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsA"
    "AcEpxV8AA=="
)
MOCK_START_STREAM_SESSION_UUID = UUID("3303d503-17cc-469a-b672-92436a71a2f6")

PID_THAT_WILL_NEVER_BE_ALIVE = 2147483647


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
def mock_audio_proxy():
    """Mock AudioProxy to avoid spawning real subprocesses."""
    mock_proxy = MagicMock()
    mock_proxy.local_port = MOCK_AUDIO_PROXY_PORT
    mock_proxy.async_start = AsyncMock()
    mock_proxy.async_stop = AsyncMock()

    with patch(
        "homeassistant.components.homekit.type_cameras.AudioProxy",
        return_value=mock_proxy,
    ):
        yield mock_proxy


async def _async_start_streaming(hass: HomeAssistant, acc: Camera) -> None:
    """Start streaming a camera."""
    acc.set_selected_stream_configuration(MOCK_START_STREAM_TLV)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()


async def _async_setup_endpoints(hass: HomeAssistant, acc: Camera) -> None:
    """Set camera endpoints."""
    acc.set_endpoints(MOCK_END_POINTS_TLV)
    acc.run()
    await hass.async_block_till_done()


async def _async_reconfigure_stream(
    hass: HomeAssistant,
    acc: Camera,
    session_info: dict[str, Any],
    stream_config: dict[str, Any],
) -> None:
    """Reconfigure the stream."""
    await acc.reconfigure_stream(session_info, stream_config)
    acc.run()
    await hass.async_block_till_done()


async def _async_stop_all_streams(hass: HomeAssistant, acc: Camera) -> None:
    """Stop all camera streams."""
    await acc.stop()
    acc.run()
    await hass.async_block_till_done()


async def _async_stop_stream(
    hass: HomeAssistant, acc: Camera, session_info: dict[str, Any]
) -> None:
    """Stop a camera stream."""
    await acc.stop_stream(session_info)
    acc.run()
    await hass.async_block_till_done()


def _mock_reader():
    """Mock ffmpeg reader."""

    async def _readline(*args, **kwargs):
        await asyncio.sleep(0.1)

    async def _get_reader(*args, **kwargs):
        return AsyncMock(readline=_readline)

    return _get_reader


def _get_exits_after_startup_mock_ffmpeg():
    """Return a ffmpeg that will have an invalid pid."""
    ffmpeg = MagicMock()
    type(ffmpeg.process).pid = PropertyMock(return_value=PID_THAT_WILL_NEVER_BE_ALIVE)
    ffmpeg.open = AsyncMock(return_value=True)
    ffmpeg.close = AsyncMock(return_value=True)
    ffmpeg.kill = AsyncMock(return_value=True)
    ffmpeg.get_reader = _mock_reader()
    return ffmpeg


def _get_working_mock_ffmpeg():
    """Return a working ffmpeg."""
    ffmpeg = MagicMock()
    ffmpeg.open = AsyncMock(return_value=True)
    ffmpeg.close = AsyncMock(return_value=True)
    ffmpeg.kill = AsyncMock(return_value=True)
    ffmpeg.get_reader = _mock_reader()
    return ffmpeg


def _get_failing_mock_ffmpeg():
    """Return an ffmpeg that fails to shutdown."""
    ffmpeg = MagicMock()
    type(ffmpeg.process).pid = PropertyMock(return_value=PID_THAT_WILL_NEVER_BE_ALIVE)
    ffmpeg.open = AsyncMock(return_value=False)
    ffmpeg.close = AsyncMock(side_effect=OSError)
    ffmpeg.kill = AsyncMock(side_effect=OSError)
    ffmpeg.get_reader = _mock_reader()
    return ffmpeg


async def test_camera_stream_source_configured(hass: HomeAssistant, run_driver) -> None:
    """Test a camera that can stream with a configured source."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {CONF_STREAM_SOURCE: "/dev/null", CONF_SUPPORT_AUDIO: True},
    )
    not_camera_acc = Switch(
        hass,
        run_driver,
        "Switch",
        entity_id,
        4,
        {},
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)
    bridge.add_accessory(not_camera_acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    working_ffmpeg = _get_working_mock_ffmpeg()
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v libx264 -profile:v high "
        "-tune zerolatency -pix_fmt yuv420p -r 30 -b:v 299k "
        "-bufsize 1196k -maxrate 299k -payload_type 99 "
        "-ssrc {v_ssrc} -f rtp -srtp_out_suite "
        "AES_CM_128_HMAC_SHA1_80 -srtp_out_params "
        "zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246"
        "?rtcpport=51246&localrtpport=51246&pkt_size=1316 "
        "-map 0:a:0 -vn -c:a libopus -application lowdelay "
        "-ac 1 -ar 24k -b:a 24k -bufsize 96k "
        "-frame_duration 20 -payload_type 110 "
        f"-ssrc {{a_ssrc}} -f rtp "
        f"rtp://127.0.0.1:{MOCK_AUDIO_PROXY_PORT}?pkt_size=188"
    )

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
        extra_cmd="-hide_banner -nostats",
        stderr_pipe=True,
    )

    await _async_setup_endpoints(hass, acc)
    working_ffmpeg = _get_working_mock_ffmpeg()
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="rtsp://example.local",
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)
        # Calling a second time should not throw
        await _async_stop_all_streams(hass, acc)

    turbo_jpeg = mock_turbo_jpeg(
        first_width=16, first_height=12, second_width=300, second_height=200
    )
    with patch("turbojpeg.TurboJPEG", return_value=turbo_jpeg):
        TurboJPEGSingleton()
        assert await acc.async_get_snapshot(
            {"aid": 2, "image-width": 300, "image-height": 200}
        )
        # Verify the bridge only forwards async_get_snapshot for
        # cameras and valid accessory ids
        assert await bridge.async_get_snapshot(
            {"aid": 2, "image-width": 300, "image-height": 200}
        )

    with pytest.raises(ValueError):
        assert await bridge.async_get_snapshot(
            {"aid": 3, "image-width": 300, "image-height": 200}
        )

    with pytest.raises(ValueError):
        assert await bridge.async_get_snapshot(
            {"aid": 4, "image-width": 300, "image-height": 200}
        )


async def test_camera_stream_source_configured_with_failing_ffmpeg(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera that can stream with a configured source with ffmpeg failing."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {CONF_STREAM_SOURCE: "/dev/null", CONF_SUPPORT_AUDIO: True},
    )
    not_camera_acc = Switch(
        hass,
        run_driver,
        "Switch",
        entity_id,
        4,
        {},
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)
    bridge.add_accessory(not_camera_acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="rtsp://example.local",
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=_get_failing_mock_ffmpeg(),
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)
        # Calling a second time should not throw
        await _async_stop_all_streams(hass, acc)


async def test_camera_stream_source_audio_proxy_fails(
    hass: HomeAssistant, run_driver, mock_audio_proxy: MagicMock
) -> None:
    """Test streaming continues without audio when audio proxy fails to start."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {CONF_STREAM_SOURCE: "/dev/null", CONF_SUPPORT_AUDIO: True},
    )

    acc.run()
    await _async_setup_endpoints(hass, acc)

    # Simulate audio proxy failing to bind a port
    mock_audio_proxy.local_port = 0
    working_ffmpeg = _get_working_mock_ffmpeg()

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)

    mock_audio_proxy.async_stop.assert_called()


async def test_camera_stream_source_found(hass: HomeAssistant, run_driver) -> None:
    """Test a camera that can stream and we get the source from the entity."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {},
    )
    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    working_ffmpeg = _get_working_mock_ffmpeg()
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="rtsp://example.local",
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v libx264 -profile:v high "
        "-tune zerolatency -pix_fmt yuv420p -r 30 -b:v 299k "
        "-bufsize 1196k -maxrate 299k -payload_type 99 "
        "-ssrc {v_ssrc} -f rtp -srtp_out_suite "
        "AES_CM_128_HMAC_SHA1_80 -srtp_out_params "
        "zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246"
        "?rtcpport=51246&localrtpport=51246&pkt_size=1316"
    )

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i rtsp://example.local",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
        extra_cmd="-hide_banner -nostats",
        stderr_pipe=True,
    )

    await _async_setup_endpoints(hass, acc)
    working_ffmpeg = _get_working_mock_ffmpeg()
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value="rtsp://example2.local",
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i rtsp://example2.local",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
        extra_cmd="-hide_banner -nostats",
        stderr_pipe=True,
    )


async def test_camera_stream_source_fails(hass: HomeAssistant, run_driver) -> None:
    """Test a camera that can stream and we cannot get the source from the entity."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {},
    )
    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            side_effect=OSError,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=_get_working_mock_ffmpeg(),
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)


async def test_camera_with_no_stream(hass: HomeAssistant, run_driver) -> None:
    """Test a camera that cannot stream."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(hass, camera.DOMAIN, {camera.DOMAIN: {}})

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {},
    )
    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    await _async_start_streaming(hass, acc)
    await _async_stop_all_streams(hass, acc)

    with pytest.raises(HomeAssistantError):
        assert await acc.async_get_snapshot(
            {"aid": 2, "image-width": 300, "image-height": 200}
        )


async def test_camera_stream_source_configured_and_copy_codec(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera that can stream with a configured source."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_COPY,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    working_ffmpeg = _get_working_mock_ffmpeg()

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_reconfigure_stream(hass, acc, session_info, {})
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v copy -tune zerolatency "
        "-pix_fmt yuv420p -r 30 -b:v 299k -bufsize 1196k "
        "-maxrate 299k -payload_type 99 -ssrc {v_ssrc} -f "
        "rtp -srtp_out_suite AES_CM_128_HMAC_SHA1_80 "
        "-srtp_out_params "
        "zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246"
        "?rtcpport=51246&localrtpport=51246&pkt_size=1316 "
        "-map 0:a:0 -vn -c:a copy -ac 1 -ar 24k "
        "-b:a 24k -bufsize 96k "
        f"-payload_type 110 -ssrc {{a_ssrc}} -f rtp "
        f"rtp://127.0.0.1:{MOCK_AUDIO_PROXY_PORT}?pkt_size=188"
    )

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
        extra_cmd="-hide_banner -nostats",
        stderr_pipe=True,
    )


async def test_camera_stream_source_configured_and_override_profile_names(
    hass: HomeAssistant, run_driver
) -> None:
    """Test camera streaming with configured source and profile overrides."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_V4L2M2M,
            CONF_VIDEO_PROFILE_NAMES: ["0", "2", "4"],
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    working_ffmpeg = _get_working_mock_ffmpeg()

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=working_ffmpeg,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_reconfigure_stream(hass, acc, session_info, {})
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v h264_v4l2m2m -profile:v 4 "
        "-tune zerolatency -pix_fmt yuv420p -r 30 "
        "-b:v 299k -bufsize 1196k -maxrate 299k "
        "-payload_type 99 -ssrc {v_ssrc} -f rtp "
        "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 "
        "-srtp_out_params "
        "zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246"
        "?rtcpport=51246&localrtpport=51246&pkt_size=1316 "
        "-map 0:a:0 -vn -c:a copy -ac 1 -ar 24k "
        "-b:a 24k -bufsize 96k "
        f"-payload_type 110 -ssrc {{a_ssrc}} -f rtp "
        f"rtp://127.0.0.1:{MOCK_AUDIO_PROXY_PORT}?pkt_size=188"
    )

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
        extra_cmd="-hide_banner -nostats",
        stderr_pipe=True,
    )


async def test_camera_streaming_fails_after_starting_ffmpeg(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera that can stream with a configured source."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_OMX,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    ffmpeg_with_invalid_pid = _get_exits_after_startup_mock_ffmpeg()

    with (
        patch(
            "homeassistant.components.demo.camera.DemoCamera.stream_source",
            return_value=None,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=ffmpeg_with_invalid_pid,
        ),
    ):
        await _async_start_streaming(hass, acc)
        await _async_reconfigure_stream(hass, acc, session_info, {})
        # Should not throw
        await _async_stop_stream(hass, acc, {"id": "does_not_exist"})
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v h264_omx -profile:v high "
        "-tune zerolatency -pix_fmt yuv420p -r 30 "
        "-b:v 299k -bufsize 1196k -maxrate 299k "
        "-payload_type 99 -ssrc {v_ssrc} -f rtp "
        "-srtp_out_suite AES_CM_128_HMAC_SHA1_80 "
        "-srtp_out_params "
        "zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246"
        "?rtcpport=51246&localrtpport=51246&pkt_size=1316 "
        "-map 0:a:0 -vn -c:a copy -ac 1 -ar 24k "
        "-b:a 24k -bufsize 96k "
        f"-payload_type 110 -ssrc {{a_ssrc}} -f rtp "
        f"rtp://127.0.0.1:{MOCK_AUDIO_PROXY_PORT}?pkt_size=188"
    )

    ffmpeg_with_invalid_pid.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
        extra_cmd="-hide_banner -nostats",
        stderr_pipe=True,
    )


async def test_camera_with_linked_motion_sensor(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera with a linked motion sensor can update."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    motion_entity_id = "binary_sensor.motion"

    hass.states.async_set(
        motion_entity_id, STATE_ON, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_OMX,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
            CONF_LINKED_MOTION_SENSOR: motion_entity_id,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    service = acc.get_service(SERV_MOTION_SENSOR)
    assert service
    char = service.get_characteristic(CHAR_MOTION_DETECTED)
    assert char

    assert char.value is True
    broker = MagicMock()
    char.broker = broker

    hass.states.async_set(
        motion_entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 2
    broker.reset_mock()
    assert char.value is False

    char.set_value(True)
    hass.states.async_set(
        motion_entity_id, STATE_ON, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 2
    broker.reset_mock()
    assert char.value is True

    hass.states.async_set(
        motion_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION},
        force_update=True,
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    hass.states.async_set(
        motion_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 0
    broker.reset_mock()
    # Ensure we do not throw when the linked
    # motion sensor is removed
    hass.states.async_remove(motion_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert char.value is True


async def test_camera_with_linked_motion_event(hass: HomeAssistant, run_driver) -> None:
    """Test a camera with a linked motion event entity can update."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    motion_entity_id = "event.motion"

    hass.states.async_set(
        motion_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
    )
    await hass.async_block_till_done()
    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_OMX,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
            CONF_LINKED_MOTION_SENSOR: motion_entity_id,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    service = acc.get_service(SERV_MOTION_SENSOR)
    assert service
    char = service.get_characteristic(CHAR_MOTION_DETECTED)
    assert char

    assert char.value is False
    broker = MagicMock()
    char.broker = broker

    hass.states.async_set(
        motion_entity_id, STATE_UNKNOWN, {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 0
    broker.reset_mock()
    assert char.value is False

    fire_time = dt_util.utcnow().isoformat()
    hass.states.async_set(
        motion_entity_id, fire_time, {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 2
    broker.reset_mock()
    # Motion stays detected so HomeKit receives the event before it resets.
    assert char.value is True

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MOTION_EVENT_RESET_SECONDS)
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 2
    broker.reset_mock()
    assert char.value is False

    hass.states.async_set(
        motion_entity_id,
        fire_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
        force_update=True,
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    hass.states.async_set(
        motion_entity_id,
        fire_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert len(broker.mock_calls) == 0
    broker.reset_mock()
    # Ensure we do not throw when the linked
    # motion sensor is removed
    hass.states.async_remove(motion_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert char.value is False

    # Ensure re-adding does not fire an event
    hass.states.async_set(
        motion_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert not broker.mock_calls

    # But a second update does
    broker.reset_mock()
    hass.states.async_set(
        motion_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
    )
    await hass.async_block_till_done()
    assert broker.mock_calls
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=MOTION_EVENT_RESET_SECONDS)
    )
    await hass.async_block_till_done()

    # Now go unavailable
    broker.reset_mock()
    hass.states.async_set(
        motion_entity_id,
        STATE_UNAVAILABLE,
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
    )
    await hass.async_block_till_done()
    assert not broker.mock_calls

    # Going from unavailable to a state should not fire an event
    hass.states.async_set(
        motion_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
    )
    await hass.async_block_till_done()
    assert not broker.mock_calls

    # But a another update does
    broker.reset_mock()
    hass.states.async_set(
        motion_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert broker.mock_calls


async def test_camera_linked_motion_event_resets_after_last_event(
    hass: HomeAssistant, run_driver: HomeDriver, freezer: FrozenDateTimeFactory
) -> None:
    """Test a new motion event extends the hold and stopping cancels it."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    motion_entity_id = "event.motion"
    hass.states.async_set(
        motion_entity_id,
        "2025-01-01T00:00:00+00:00",
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
    )
    entity_id = "camera.demo_camera"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {CONF_STREAM_SOURCE: "/dev/null", CONF_LINKED_MOTION_SENSOR: motion_entity_id},
    )
    acc.run()
    char = acc.get_service(SERV_MOTION_SENSOR).get_characteristic(CHAR_MOTION_DETECTED)
    hold = timedelta(seconds=MOTION_EVENT_RESET_SECONDS)

    for _ in range(2):
        hass.states.async_set(
            motion_entity_id,
            dt_util.utcnow().isoformat(),
            {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
        )
        await hass.async_block_till_done()
        freezer.tick(hold / 2)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # The second event restarted the hold.
    assert char.value is True
    freezer.tick(hold / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert char.value is False

    hass.states.async_set(
        motion_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.MOTION},
    )
    await hass.async_block_till_done()
    acc.async_stop()
    freezer.tick(hold)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # Stopping cancelled the reset.
    assert char.value is True


async def test_camera_with_a_missing_linked_motion_sensor(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera with a configured linked motion sensor that is missing."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    motion_entity_id = "binary_sensor.motion"
    entity_id = "camera.demo_camera"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {CONF_LINKED_MOTION_SENSOR: motion_entity_id},
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    assert not acc.get_service(SERV_MOTION_SENSOR)


async def test_camera_with_linked_doorbell_sensor(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera with a linked doorbell sensor can update."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    doorbell_entity_id = "binary_sensor.doorbell"

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
    )
    await hass.async_block_till_done()
    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_OMX,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
            CONF_LINKED_DOORBELL_SENSOR: doorbell_entity_id,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    service = acc.get_service(SERV_DOORBELL)
    assert service
    char = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char

    assert char.value is None

    service2 = acc.get_service(SERV_STATELESS_PROGRAMMABLE_SWITCH)
    assert service2
    char2 = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char2
    broker = MagicMock()
    char2.broker = broker
    assert char2.value is None

    hass.states.async_set(
        doorbell_entity_id,
        STATE_OFF,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0

    char.set_value(True)
    char2.set_value(True)
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
        force_update=True,
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    # Ensure we do not throw when the linked
    # doorbell sensor is removed
    hass.states.async_remove(doorbell_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None


async def test_camera_with_linked_doorbell_event(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera with a linked doorbell event can update."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    doorbell_entity_id = "event.doorbell"

    hass.states.async_set(
        doorbell_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_OMX,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
            CONF_LINKED_DOORBELL_SENSOR: doorbell_entity_id,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    service = acc.get_service(SERV_DOORBELL)
    assert service
    char = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char

    assert char.value is None

    service2 = acc.get_service(SERV_STATELESS_PROGRAMMABLE_SWITCH)
    assert service2
    char2 = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char2
    broker = MagicMock()
    char2.broker = broker
    assert char2.value is None

    hass.states.async_set(
        doorbell_entity_id,
        STATE_UNKNOWN,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0

    char.set_value(True)
    char2.set_value(True)
    broker.reset_mock()

    original_time = dt_util.utcnow().isoformat()
    hass.states.async_set(
        doorbell_entity_id,
        original_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        original_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
        force_update=True,
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        original_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    # Ensure we do not throw when the linked
    # doorbell sensor is removed
    hass.states.async_remove(doorbell_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None

    await hass.async_block_till_done()
    hass.states.async_set(
        doorbell_entity_id,
        STATE_UNAVAILABLE,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    # Ensure re-adding does not fire an event
    assert not broker.mock_calls
    broker.reset_mock()

    # going from unavailable to a state should not fire an event
    hass.states.async_set(
        doorbell_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert not broker.mock_calls

    # But a second update does
    hass.states.async_set(
        doorbell_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert broker.mock_calls


async def test_camera_with_a_missing_linked_doorbell_sensor(
    hass: HomeAssistant, run_driver
) -> None:
    """Test a camera with a configured linked doorbell sensor that is missing."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    doorbell_entity_id = "binary_sensor.doorbell"
    entity_id = "camera.demo_camera"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(
        hass,
        run_driver,
        "Camera",
        entity_id,
        2,
        {CONF_LINKED_DOORBELL_SENSOR: doorbell_entity_id},
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    assert not acc.get_service(SERV_DOORBELL)
    assert not acc.get_service(SERV_STATELESS_PROGRAMMABLE_SWITCH)


RECORDING_SELECTION = SelectedRecordingConfiguration(
    recording=SupportedRecordingConfiguration(),
    video=VideoCodecConfiguration(
        codec_type=VideoCodecType.H264,
        profile=2,
        level=2,
        bitrate_kbps=2000,
        iframe_interval_ms=4000,
        attributes=[VideoAttributes(width=1920, height=1080, frame_rate=30)],
    ),
    audio=AudioCodecConfiguration(sample_rate=AudioSampleRate.KHZ_32),
)
RECORDING_FILTER = (
    "scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"
)
RECORDING_SCALE = f"-vf '{RECORDING_FILTER}'"
RECORDING_RATE = (
    "-r 30 -b:v 2000k -maxrate 2000k -bufsize 4000k -bf 0 -g 120 "
    "-force_key_frames expr:gte(t,n_forced*4) -sc_threshold 0"
)
RECORDING_TRANSCODE = (
    "-map 0:v:0 -c:v libx264 -profile:v high -level:v 4.0 "
    f"-preset veryfast -tune zerolatency -pix_fmt yuv420p {RECORDING_SCALE} "
    f"{RECORDING_RATE}"
)
RECORDING_HARDWARE_TRANSCODE = (
    "-map 0:v:0 -c:v h264_v4l2m2m -profile:v 1 -pix_fmt yuv420p "
    f"{RECORDING_SCALE} {RECORDING_RATE}"
)
RECORDING_AUDIO = "-c:a aac -profile:a aac_low -ac 1 -ar 32000 -b:a 64k"
RECORDING_SILENT_INPUT = " -f lavfi -i anullsrc=channel_layout=mono:sample_rate=32000"
RECORDING_CONTAINER = (
    "-shortest -f mp4 "
    "-movflags frag_keyframe+empty_moov+default_base_moof+skip_trailer -"
)


@pytest.mark.parametrize(
    ("config", "source", "audio_active", "expected_input", "expected_output"),
    [
        pytest.param(
            {CONF_SUPPORT_AUDIO: True},
            "rtsp://cam",
            True,
            "-i rtsp://cam",
            f"{RECORDING_TRANSCODE} -map 0:a:0 {RECORDING_AUDIO} {RECORDING_CONTAINER}",
            id="transcode_with_audio",
        ),
        pytest.param(
            {CONF_SUPPORT_AUDIO: True},
            "rtsp://cam",
            False,
            "-i rtsp://cam" + RECORDING_SILENT_INPUT,
            f"{RECORDING_TRANSCODE} -map 1:a:0 {RECORDING_AUDIO} {RECORDING_CONTAINER}",
            id="recording_audio_off",
        ),
        pytest.param(
            {},
            "rtsp://cam",
            True,
            "-i rtsp://cam" + RECORDING_SILENT_INPUT,
            f"{RECORDING_TRANSCODE} -map 1:a:0 {RECORDING_AUDIO} {RECORDING_CONTAINER}",
            id="camera_without_audio",
        ),
        pytest.param(
            {CONF_VIDEO_CODEC: VIDEO_CODEC_COPY},
            "rtsp://cam",
            True,
            "-i rtsp://cam" + RECORDING_SILENT_INPUT,
            f"-map 0:v:0 -c:v copy -map 1:a:0 {RECORDING_AUDIO} {RECORDING_CONTAINER}",
            id="video_copy",
        ),
        pytest.param(
            {
                CONF_VIDEO_CODEC: VIDEO_CODEC_H264_V4L2M2M,
                CONF_VIDEO_PROFILE_NAMES: ["4", "2", "1"],
            },
            "rtsp://cam",
            True,
            "-i rtsp://cam" + RECORDING_SILENT_INPUT,
            f"{RECORDING_HARDWARE_TRANSCODE} -map 1:a:0 {RECORDING_AUDIO} "
            f"{RECORDING_CONTAINER}",
            id="hardware_encoder_without_level",
        ),
        pytest.param(
            {CONF_SUPPORT_AUDIO: True},
            "-rtsp_transport tcp -i rtsp://cam -i rtsp://mic",
            False,
            "-rtsp_transport tcp -i rtsp://cam -i rtsp://mic" + RECORDING_SILENT_INPUT,
            f"{RECORDING_TRANSCODE} -map 2:a:0 {RECORDING_AUDIO} {RECORDING_CONTAINER}",
            id="silent_audio_after_configured_inputs",
        ),
        pytest.param(
            {CONF_SUPPORT_AUDIO: True},
            "-i rtsp://cam -vf \"drawtext=text='Front door'\" -filter:v hflip",
            True,
            "-i rtsp://cam",
            RECORDING_TRANSCODE.replace(
                RECORDING_SCALE,
                "-vf 'hflip,drawtext=text='\"'\"'Front door'\"'\"',"
                f"{RECORDING_FILTER}'",
            )
            + f" -map 0:a:0 {RECORDING_AUDIO} {RECORDING_CONTAINER}",
            id="source_filters_before_scaling",
        ),
    ],
)
def test_recording_ffmpeg_args(
    config: dict[str, Any],
    source: str,
    audio_active: bool,
    expected_input: str,
    expected_output: str,
) -> None:
    """Test the ffmpeg arguments for a HomeKit Secure Video recording."""
    assert recording_ffmpeg_args(
        {**CONFIG_DEFAULTS, **config}, RECORDING_SELECTION, source, audio_active
    ) == (expected_input, expected_output)


MOTION_SENSOR = "binary_sensor.motion"
CAMERA_ENTITY = "camera.front"
SECURE_VIDEO_CONFIG = {
    CONF_STREAM_SOURCE: "rtsp://cam",
    CONF_LINKED_MOTION_SENSOR: MOTION_SENSOR,
    CONF_CAMERA_MODE: CAMERA_MODE_SECURE_VIDEO,
}


def _box(box_type: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I", 8 + len(payload)) + box_type + payload


INIT_SEGMENT = _box(b"ftyp", b"isom") + _box(b"moov", b"m")
FRAGMENT = _box(b"moof", b"f") + _box(b"mdat", b"d")


async def _secure_video_camera(
    hass: HomeAssistant, driver: HomeDriver, aid: int = STANDALONE_AID, **config: Any
) -> Camera:
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set(CAMERA_ENTITY, "idle")
    hass.states.async_set(
        MOTION_SENSOR, STATE_ON, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    return Camera(
        hass, driver, "Camera", CAMERA_ENTITY, aid, {**SECURE_VIDEO_CONFIG, **config}
    )


@pytest.fixture
async def no_state_file(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Keep recording state changes from writing the accessory state file."""
    with patch("pyhap.accessory_driver.AccessoryDriver.async_persist"):
        yield
        # pyhap saves on a later loop iteration.
        await hass.async_block_till_done()


async def _recording_camera(
    hass: HomeAssistant, driver: HomeDriver, **config: Any
) -> Camera:
    """Return a camera the home hub has selected a recording format for."""
    acc = await _secure_video_camera(hass, driver, **config)
    acc.set_selected_recording_configuration(
        to_base64_str(RECORDING_SELECTION.encode())
    )
    return acc


def _closed_pipe(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


def _ffmpeg_output(
    stream: MagicMock, stdout: asyncio.StreamReader, stderr: asyncio.StreamReader
) -> None:
    """Set the pipes of the recording ffmpeg."""
    pipes = {"stdout": stdout, "stderr": stderr}
    stream.get_reader = AsyncMock(side_effect=lambda source="stdout": pipes[source])


@pytest.fixture
def recording_ffmpeg() -> Generator[MagicMock]:
    """Patch the recording ffmpeg with one that streams a fragmented MP4."""
    stream = MagicMock(is_running=True)
    stream.open = AsyncMock(return_value=True)
    _ffmpeg_output(
        stream,
        _closed_pipe(INIT_SEGMENT + FRAGMENT),
        _closed_pipe(b"Connection refused\n"),
    )
    stream.process.wait = AsyncMock(return_value=0)
    with patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg", return_value=stream
    ):
        yield stream


async def _collect(acc: Camera) -> list[RecordingPacket]:
    return [packet async for packet in acc.handle_recording_stream(1)]


async def test_camera_secure_video(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_transport: tuple[AsyncMock, AsyncMock],
) -> None:
    """Test recording uses one motion sensor and runs the recording transport."""
    acc = await _secure_video_camera(hass, run_driver)
    start, stop = recording_transport

    assert acc.get_service("CameraRecordingManagement")
    assert [s.display_name for s in acc.services].count(SERV_MOTION_SENSOR) == 1
    char = acc.get_service(SERV_MOTION_SENSOR).get_characteristic(CHAR_MOTION_DETECTED)
    assert char.value is True

    acc.run()
    await hass.async_block_till_done()
    start.assert_awaited_once_with()

    hass.states.async_set(
        MOTION_SENSOR, STATE_OFF, {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION}
    )
    await hass.async_block_till_done()
    assert char.value is False

    await acc.stop()
    stop.assert_awaited_once_with()


@pytest.mark.usefixtures("recording_transport")
async def test_camera_secure_video_keeps_motion_iid(
    hass: HomeAssistant,
    run_driver: HomeDriver,
) -> None:
    """Test enabling recording keeps the motion sensor of existing pairings."""

    def motion_iid(acc: Camera) -> int:
        service = acc.get_service(SERV_MOTION_SENSOR)
        return acc.iid_manager.get_iid(service.get_characteristic(CHAR_MOTION_DETECTED))

    before = motion_iid(
        await _secure_video_camera(
            hass, run_driver, **{CONF_CAMERA_MODE: CAMERA_MODE_STANDARD}
        )
    )
    assert motion_iid(await _secure_video_camera(hass, run_driver)) == before


@pytest.mark.parametrize(
    ("aid", "config", "message"),
    [
        pytest.param(
            STANDALONE_AID,
            {CONF_LINKED_MOTION_SENSOR: None},
            "needs a linked motion sensor",
            id="no_motion_sensor",
        ),
        pytest.param(2, {}, "needs the camera in accessory mode", id="bridged"),
    ],
)
async def test_camera_secure_video_not_possible(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    caplog: pytest.LogCaptureFixture,
    aid: int,
    config: dict[str, Any],
    message: str,
) -> None:
    """Test cameras that cannot record do not offer recording."""
    with caplog.at_level(logging.WARNING):
        acc = await _secure_video_camera(hass, run_driver, aid, **config)
    assert acc.get_service("CameraRecordingManagement") is None
    assert acc.diagnostics() == {}
    assert message in caplog.text


async def test_camera_secure_video_reload_stops_transport(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_transport: tuple[AsyncMock, AsyncMock],
) -> None:
    """Test an in-place reload, which only calls async_stop, closes the listener."""
    acc = await _secure_video_camera(hass, run_driver)
    acc.async_stop()
    await hass.async_block_till_done()
    recording_transport[1].assert_awaited_once_with()


@pytest.mark.parametrize(
    ("config", "audio_active", "expected_output"),
    [
        pytest.param({}, 1, "-map 0:a:0", id="audio"),
        pytest.param({}, 0, "-map 1:a:0", id="silent"),
        pytest.param({CONF_VIDEO_CODEC: VIDEO_CODEC_COPY}, 1, "-c:v copy", id="copy"),
    ],
)
@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
    config: dict[str, Any],
    audio_active: int,
    expected_output: str,
) -> None:
    """Test a recording streams the ffmpeg fragments and kills ffmpeg after."""
    # A stderr that stays open until ffmpeg is killed, like a real one.
    stderr = asyncio.StreamReader()
    _ffmpeg_output(recording_ffmpeg, _closed_pipe(INIT_SEGMENT + FRAGMENT), stderr)
    kill_reads: list[asyncio.Task[bytes]] = []

    def kill() -> None:
        # HAFFmpeg.kill() reads the remaining output in a background task.
        kill_reads.append(hass.async_create_task(stderr.read()))
        stderr.feed_eof()

    recording_ffmpeg.kill.side_effect = kill
    acc = await _recording_camera(
        hass, run_driver, **{CONF_SUPPORT_AUDIO: True, **config}
    )
    acc.get_service("CameraRecordingManagement").get_characteristic(
        "RecordingAudioActive"
    ).set_value(audio_active)

    packets = await _collect(acc)

    assert [packet.data for packet in packets] == [INIT_SEGMENT, FRAGMENT, b""]
    assert packets[-1].is_last
    assert "without video" not in caplog.text
    open_kwargs = recording_ffmpeg.open.await_args.kwargs
    assert open_kwargs["input_source"].startswith("-i rtsp://cam")
    assert expected_output in open_kwargs["output"]
    recording_ffmpeg.kill.assert_called_once_with()
    # A second reader on stderr would fail.
    assert await kill_reads[0] == b""


URL_ERROR = b"rtsps://user:secret@cam:7441/token: Connection refused\n"


@pytest.mark.parametrize(
    ("output", "stderr", "returncode", "message"),
    [
        pytest.param(
            INIT_SEGMENT + FRAGMENT,
            URL_ERROR,
            1,
            "Recording ffmpeg exited with 1: <url>: Connection refused",
            id="fails_mid_recording",
        ),
        pytest.param(
            b"",
            URL_ERROR,
            1,
            "Recording ffmpeg exited with 1: <url>: Connection refused",
            id="fails_before_output",
        ),
        pytest.param(
            b"",
            b"End of file\n",
            0,
            "Recording ffmpeg ended without video: End of file",
            id="no_output",
        ),
        pytest.param(
            INIT_SEGMENT, b"", 0, "Recording ffmpeg ended without video", id="init_only"
        ),
    ],
)
@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_incomplete(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
    output: bytes,
    stderr: bytes,
    returncode: int,
    message: str,
) -> None:
    """Test a failed recording is logged and not ended as complete."""
    _ffmpeg_output(recording_ffmpeg, _closed_pipe(output), _closed_pipe(stderr))
    recording_ffmpeg.process.wait.return_value = returncode
    acc = await _recording_camera(hass, run_driver)

    packets = await _collect(acc)

    assert not any(packet.is_last for packet in packets)
    assert message in caplog.text
    assert "secret" not in caplog.text
    assert "token" not in caplog.text


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_ffmpeg_hangs(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ffmpeg that does not exit after its output ends is killed."""
    # The first wait hangs, the second is the one after the kill.
    waits = iter([asyncio.Event().wait(), asyncio.sleep(0, 0)])
    recording_ffmpeg.process.wait = lambda: next(waits)
    acc = await _recording_camera(hass, run_driver)

    with patch(
        "homeassistant.components.homekit.type_cameras.RECORDING_EXIT_TIMEOUT", 0.01
    ):
        packets = await _collect(acc)

    assert not any(packet.is_last for packet in packets)
    assert "did not exit after its output ended" in caplog.text
    recording_ffmpeg.kill.assert_called_once_with()


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(b"", id="nothing"),
        pytest.param(INIT_SEGMENT, id="init_only"),
        pytest.param(INIT_SEGMENT + FRAGMENT, id="after_video"),
    ],
)
@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_stalls(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
    output: bytes,
) -> None:
    """Test a recording ends when ffmpeg stops delivering fragments."""
    stdout = asyncio.StreamReader()
    stdout.feed_data(output)
    _ffmpeg_output(recording_ffmpeg, stdout, _closed_pipe(b""))
    acc = await _recording_camera(hass, run_driver)

    with patch("homeassistant.components.homekit.type_cameras.RECORDING_TIMEOUT", 0.01):
        packets = await _collect(acc)
    assert b"".join(packet.data for packet in packets) == output
    assert "ffmpeg delivered no video for 0.01 seconds" in caplog.text
    recording_ffmpeg.kill.assert_called_once_with()


@pytest.mark.parametrize(
    ("config", "open_calls", "message"),
    [
        pytest.param(
            {CONF_STREAM_SOURCE: None},
            0,
            "Camera has no stream source",
            id="no_stream_source",
        ),
        pytest.param(
            {CONF_STREAM_SOURCE: "rtsp://user:pa'ss@cam"},
            0,
            "Cannot build the recording: No closing quotation",
            id="unbalanced_quote",
        ),
        pytest.param(
            {CONF_VIDEO_PROFILE_NAMES: ["baseline"]},
            0,
            "Cannot build the recording: list index out of range",
            id="unknown_profile",
        ),
        pytest.param(
            {CONF_STREAM_SOURCE: "-i rtsp://cam -vf"},
            0,
            "Cannot build the recording: -vf without a filter",
            id="filter_flag_without_filter",
        ),
        pytest.param({}, 1, "Failed to start recording ffmpeg", id="ffmpeg_fails"),
    ],
)
@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_cannot_start(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
    config: dict[str, Any],
    open_calls: int,
    message: str,
) -> None:
    """Test a recording that cannot start is logged and yields nothing."""
    recording_ffmpeg.open.return_value = False
    acc = await _recording_camera(hass, run_driver, **config)
    with patch(
        "homeassistant.components.camera.async_get_stream_source", return_value=None
    ):
        assert await _collect(acc) == []
    assert recording_ffmpeg.open.await_count == open_calls
    assert message in caplog.text
    recording_ffmpeg.kill.assert_not_called()


async def test_camera_secure_video_transport_fails(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_transport: tuple[AsyncMock, AsyncMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a recording listener that cannot bind is logged."""
    recording_transport[0].side_effect = OSError("Address in use")
    acc = await _secure_video_camera(hass, run_driver)
    acc.run()
    await hass.async_block_till_done()
    assert "cannot listen for recordings: Address in use" in caplog.text


def _recording_char(acc: Camera, name: str) -> bytes:
    return base64_to_bytes(
        acc.get_service("CameraRecordingManagement").get_characteristic(name).value
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            {},
            [
                (1920, 1080, 30),
                (1280, 720, 30),
                (1600, 1200, 30),
                (1440, 1080, 30),
                (1280, 960, 30),
                (1024, 768, 30),
            ],
            id="default",
        ),
        pytest.param(
            {CONF_MAX_FPS: 25, CONF_MAX_WIDTH: 640, CONF_MAX_HEIGHT: 480},
            [
                (1920, 1080, 24),
                (1280, 720, 24),
                (1600, 1200, 24),
                (1440, 1080, 24),
                (1280, 960, 24),
                (1024, 768, 24),
            ],
            id="streaming_limits_ignored",
        ),
        pytest.param(
            {CONF_MAX_FPS: 10, CONF_MAX_WIDTH: 1440, CONF_MAX_HEIGHT: 1920},
            [
                (1080, 1920, 15),
                (720, 1280, 15),
                (1200, 1600, 15),
                (1080, 1440, 15),
                (960, 1280, 15),
                (768, 1024, 15),
            ],
            id="portrait",
        ),
    ],
)
async def test_camera_secure_video_recording_formats(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    config: dict[str, Any],
    expected: list[tuple[int, int, int]],
) -> None:
    """Test recording advertises formats a home hub can select and no prebuffer."""
    acc = await _secure_video_camera(hass, run_driver, **config)

    video = decode_supported_video(
        _recording_char(acc, "SupportedVideoRecordingConfiguration")
    )
    assert [(a.width, a.height, a.frame_rate) for a in video[0].attributes] == expected
    general = SupportedRecordingConfiguration.decode(
        _recording_char(acc, "SupportedCameraRecordingConfiguration")
    )
    assert general.prebuffer_length_ms == 0


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_problem_logged_once(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test each kind of recording failure warns once until a recording succeeds."""
    acc = await _recording_camera(hass, run_driver)

    def warnings(message: str) -> int:
        return sum(
            r.levelno == logging.WARNING and message in r.getMessage()
            for r in caplog.records
        )

    recording_ffmpeg.open.return_value = False
    with caplog.at_level(logging.DEBUG):
        await _collect(acc)
        await _collect(acc)
        assert warnings("Failed to start recording ffmpeg") == 1

        acc.config[CONF_STREAM_SOURCE] = None
        with patch(
            "homeassistant.components.camera.async_get_stream_source",
            return_value=None,
        ):
            await _collect(acc)
        assert warnings("Camera has no stream source") == 1

        acc.config[CONF_STREAM_SOURCE] = "rtsp://cam"
        recording_ffmpeg.open.return_value = True
        await _collect(acc)
        recording_ffmpeg.open.return_value = False
        await _collect(acc)
    assert warnings("Failed to start recording ffmpeg") == 2


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_closed_by_hub(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
) -> None:
    """Test ffmpeg is killed when the hub ends the recording."""
    _ffmpeg_output(recording_ffmpeg, _closed_pipe(INIT_SEGMENT), _closed_pipe(b""))
    acc = await _recording_camera(hass, run_driver)

    recording = acc.handle_recording_stream(1)
    assert (await anext(recording)).data == INIT_SEGMENT
    await recording.aclose()

    recording_ffmpeg.kill.assert_called_once_with()
    recording_ffmpeg.process.wait.assert_awaited_once_with()


STREAM_AVAILABLE = tlv.encode(b"\x01", STREAMING_STATUS["AVAILABLE"], to_base64=True)
STREAM_STREAMING = tlv.encode(b"\x01", STREAMING_STATUS["STREAMING"], to_base64=True)
STOP_STREAM_TLV = tlv.encode(
    SELECTED_STREAM_CONFIGURATION_TYPES["SESSION"],
    tlv.encode(
        SETUP_TYPES["SESSION_ID"],
        MOCK_START_STREAM_SESSION_UUID.bytes,
        b"\x02",
        b"\x00",
    ),
    to_base64=True,
)


@pytest.fixture
def live_ffmpeg() -> Generator[MagicMock]:
    """Patch the live stream ffmpeg with one that keeps running."""
    ffmpeg = _get_working_mock_ffmpeg()
    with (
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=ffmpeg,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.pid_is_alive",
            return_value=True,
        ),
    ):
        yield ffmpeg


async def _live_camera(hass: HomeAssistant, driver: HomeDriver) -> Camera:
    """Return a recording camera with stream endpoints set up."""
    acc = await _secure_video_camera(hass, driver)
    await _async_setup_endpoints(hass, acc)
    return acc


def _streaming_status(acc: Camera) -> str:
    return (
        acc.get_service("CameraRTPStreamManagement")
        .get_characteristic("StreamingStatus")
        .get_value()
    )


def _set_camera_active(acc: Camera, active: int) -> None:
    acc.get_service("CameraOperatingMode").get_characteristic(
        "HomeKitCameraActive"
    ).client_update_value(active)


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_turned_off(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    live_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test turning the camera off in the Home app ends live streams."""
    acc = await _live_camera(hass, run_driver)
    await _async_start_streaming(hass, acc)
    _set_camera_active(acc, 1)
    await hass.async_block_till_done()
    live_ffmpeg.close.assert_not_awaited()

    _set_camera_active(acc, 0)
    await hass.async_block_till_done()
    live_ffmpeg.close.assert_awaited_once_with()
    assert _streaming_status(acc) == STREAM_AVAILABLE
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]
    assert not await acc.reconfigure_stream(session_info, {})

    # The controller still sends its stop for the ended stream.
    acc.set_selected_stream_configuration(STOP_STREAM_TLV)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    live_ffmpeg.close.assert_awaited_once_with()
    assert acc.sessions == {}
    assert "no such session" not in caplog.text
    assert not await acc.start_stream({"id": "new"}, {})
    with pytest.raises(HomeAssistantError, match="Camera is off"):
        await acc.async_get_snapshot({"image-width": 640, "image-height": 360})


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_turned_off_while_starting(
    hass: HomeAssistant, run_driver: HomeDriver, live_ffmpeg: MagicMock
) -> None:
    """Test a stream that started while the camera was turned off is stopped."""
    acc = await _live_camera(hass, run_driver)

    async def open_and_turn_off(**kwargs: Any) -> bool:
        _set_camera_active(acc, 0)
        return True

    live_ffmpeg.open.side_effect = open_and_turn_off
    await _async_start_streaming(hass, acc)

    live_ffmpeg.close.assert_awaited_once_with()
    assert acc.sessions == {}


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_turned_off_during_snapshot(
    hass: HomeAssistant,
    run_driver: HomeDriver,
) -> None:
    """Test a snapshot taken while the camera was turned off is not returned."""
    acc = await _secure_video_camera(hass, run_driver)

    async def image_and_turn_off(*args: Any, **kwargs: Any) -> camera.Image:
        _set_camera_active(acc, 0)
        return camera.Image("image/jpeg", b"jpeg")

    with (
        patch(
            "homeassistant.components.homekit.type_cameras.camera.async_get_image",
            side_effect=image_and_turn_off,
        ),
        pytest.raises(HomeAssistantError, match="Camera is off"),
    ):
        await acc.async_get_snapshot({"image-width": 640, "image-height": 360})


@pytest.mark.parametrize(
    ("active", "audio", "closed"),
    [
        pytest.param(1, 0, False, id="unchanged"),
        pytest.param(0, 0, True, id="recording_off"),
        pytest.param(1, 1, True, id="audio_changed"),
    ],
)
@pytest.mark.usefixtures("no_state_file", "recording_transport", "recording_ffmpeg")
async def test_camera_secure_video_recording_permissions_change(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    active: int,
    audio: int,
    closed: bool,
) -> None:
    """Test a running recording ends when the hub changes what it allows."""
    acc = await _recording_camera(hass, run_driver)
    service = acc.get_service("CameraRecordingManagement")
    service.get_characteristic("Active").set_value(1)
    recording = acc.handle_recording_stream(1)
    await anext(recording)
    acc._recording_stream = stream = MagicMock(streaming=True)

    service.get_characteristic("Active").set_value(active)
    service.get_characteristic("RecordingAudioActive").set_value(audio)
    acc.recording_state_changed()

    assert stream.close.called is closed
    await recording.aclose()


async def test_camera_secure_video_stop_waits_for_transport_start(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_transport: tuple[AsyncMock, AsyncMock],
) -> None:
    """Test the recording listener is closed after a pending start finished."""
    started = asyncio.Event()
    recording_transport[0].side_effect = started.wait
    acc = await _secure_video_camera(hass, run_driver)
    acc.run()
    stop = hass.async_create_task(acc.stop())
    await asyncio.sleep(0)
    recording_transport[1].assert_not_awaited()

    started.set()
    await stop

    recording_transport[1].assert_awaited_once_with()


@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_turned_off_new_session_keeps_slot(
    hass: HomeAssistant, run_driver: HomeDriver, live_ffmpeg: MagicMock
) -> None:
    """Test ending a stream does not free a slot a new session took meanwhile."""
    acc = await _live_camera(hass, run_driver)

    async def close_while_new_session_starts() -> None:
        # The controller stops the old session and starts a new one on the slot.
        old_session = acc.sessions.pop(MOCK_START_STREAM_SESSION_UUID)
        new_id = UUID(int=1)
        acc.sessions[new_id] = {**old_session, "id": new_id}

    live_ffmpeg.close.side_effect = close_while_new_session_starts
    await _async_start_streaming(hass, acc)
    _set_camera_active(acc, 0)
    await hass.async_block_till_done()

    assert _streaming_status(acc) == STREAM_STREAMING


@pytest.mark.parametrize(
    ("first", "rest"),
    [
        pytest.param(
            b"rtsps://user:secret@cam" + b"x" * 2**17,
            b"ret@cam:7441/token\nmore output\n",
            id="newline_arrives_later",
        ),
        pytest.param(
            b"rtsps://user:secret@cam/token" + b"x" * 2**17 + b"\nmore output\n",
            b"",
            id="newline_in_buffer",
        ),
    ],
)
@pytest.mark.usefixtures("no_state_file", "recording_transport")
async def test_camera_secure_video_recording_long_stderr_line(
    hass: HomeAssistant,
    run_driver: HomeDriver,
    recording_ffmpeg: MagicMock,
    caplog: pytest.LogCaptureFixture,
    first: bytes,
    rest: bytes,
) -> None:
    """Test an overlong ffmpeg line is dropped and the next line is still read."""
    stderr = asyncio.StreamReader()
    stderr.feed_data(first)
    _ffmpeg_output(recording_ffmpeg, _closed_pipe(INIT_SEGMENT + FRAGMENT), stderr)
    acc = await _recording_camera(hass, run_driver)

    with caplog.at_level(logging.DEBUG):
        recording = acc.handle_recording_stream(1)
        assert (await anext(recording)).data == INIT_SEGMENT
        stderr.feed_data(rest)
        stderr.feed_eof()
        # Let the stderr reader catch up before the recording ends.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert [packet.data async for packet in recording] == [FRAGMENT, b""]
    assert "Recording ffmpeg: more output" in caplog.text
    assert "token" not in caplog.text
