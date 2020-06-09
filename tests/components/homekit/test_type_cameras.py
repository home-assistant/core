"""Test different accessory types: Camera."""

from uuid import UUID

from pyhap.accessory_driver import AccessoryDriver
import pytest

from homeassistant.components import camera, ffmpeg
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    AUDIO_CODEC_COPY,
    CONF_AUDIO_CODEC,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    VIDEO_CODEC_COPY,
    VIDEO_CODEC_H264_OMX,
)
from homeassistant.components.homekit.img_util import TurboJPEGSingleton
from homeassistant.components.homekit.type_cameras import Camera
from homeassistant.components.homekit.type_switches import Switch
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import mock_turbo_jpeg

from tests.async_mock import AsyncMock, MagicMock, PropertyMock, patch

MOCK_START_STREAM_TLV = "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
MOCK_END_POINTS_TLV = "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
MOCK_START_STREAM_SESSION_UUID = UUID("3303d503-17cc-469a-b672-92436a71a2f6")

PID_THAT_WILL_NEVER_BE_ALIVE = 2147483647


async def _async_start_streaming(hass, acc):
    """Start streaming a camera."""
    acc.set_selected_stream_configuration(MOCK_START_STREAM_TLV)
    await acc.run_handler()
    await hass.async_block_till_done()


async def _async_setup_endpoints(hass, acc):
    """Set camera endpoints."""
    acc.set_endpoints(MOCK_END_POINTS_TLV)
    await acc.run_handler()
    await hass.async_block_till_done()


async def _async_reconfigure_stream(hass, acc, session_info, stream_config):
    """Reconfigure the stream."""
    await acc.reconfigure_stream(session_info, stream_config)
    await acc.run_handler()
    await hass.async_block_till_done()


async def _async_stop_all_streams(hass, acc):
    """Stop all camera streams."""
    await acc.stop()
    await acc.run_handler()
    await hass.async_block_till_done()


async def _async_stop_stream(hass, acc, session_info):
    """Stop a camera stream."""
    await acc.stop_stream(session_info)
    await acc.run_handler()
    await hass.async_block_till_done()


@pytest.fixture()
def run_driver(hass):
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch("pyhap.accessory_driver.Zeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer"), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist"
    ):
        yield AccessoryDriver(
            pincode=b"123-45-678", address="127.0.0.1", loop=hass.loop
        )


def _get_exits_after_startup_mock_ffmpeg():
    """Return a ffmpeg that will have an invalid pid."""
    ffmpeg = MagicMock()
    type(ffmpeg.process).pid = PropertyMock(return_value=PID_THAT_WILL_NEVER_BE_ALIVE)
    ffmpeg.open = AsyncMock(return_value=True)
    ffmpeg.close = AsyncMock(return_value=True)
    ffmpeg.kill = AsyncMock(return_value=True)
    return ffmpeg


def _get_working_mock_ffmpeg():
    """Return a working ffmpeg."""
    ffmpeg = MagicMock()
    ffmpeg.open = AsyncMock(return_value=True)
    ffmpeg.close = AsyncMock(return_value=True)
    ffmpeg.kill = AsyncMock(return_value=True)
    return ffmpeg


def _get_failing_mock_ffmpeg():
    """Return an ffmpeg that fails to shutdown."""
    ffmpeg = MagicMock()
    type(ffmpeg.process).pid = PropertyMock(return_value=PID_THAT_WILL_NEVER_BE_ALIVE)
    ffmpeg.open = AsyncMock(return_value=False)
    ffmpeg.close = AsyncMock(side_effect=OSError)
    ffmpeg.kill = AsyncMock(side_effect=OSError)
    return ffmpeg


async def test_camera_stream_source_configured(hass, run_driver, events):
    """Test a camera that can stream with a configured source."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
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
        {CONF_STREAM_SOURCE: "/dev/null", CONF_SUPPORT_AUDIO: True},
    )
    not_camera_acc = Switch(hass, run_driver, "Switch", entity_id, 4, {},)
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)
    bridge.add_accessory(not_camera_acc)

    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    working_ffmpeg = _get_working_mock_ffmpeg()
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=None,
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=working_ffmpeg,
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v libx264 -profile:v high -tune zerolatency -pix_fmt "
        "yuv420p -r 30 -b:v 299k -bufsize 1196k -maxrate 299k -payload_type 99 -ssrc {v_ssrc} -f "
        "rtp -srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params "
        "zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246?rtcpport=51246&localrtcpport=51246&pkt_size=1316 -map 0:a:0 "
        "-vn -c:a libopus -application lowdelay -ac 1 -ar 24k -b:a 24k -bufsize 96k -payload_type "
        "110 -ssrc {a_ssrc} -f rtp -srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params "
        "shnETgfD+7xUQ8zRdsaytY11wu6CO73IJ+RZVJpU "
        "srtp://192.168.208.5:51108?rtcpport=51108&localrtcpport=51108&pkt_size=188"
    )

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
    )

    await _async_setup_endpoints(hass, acc)
    working_ffmpeg = _get_working_mock_ffmpeg()
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=working_ffmpeg,
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
        assert await hass.async_add_executor_job(
            acc.get_snapshot, {"aid": 2, "image-width": 300, "image-height": 200}
        )
        # Verify the bridge only forwards get_snapshot for
        # cameras and valid accessory ids
        assert await hass.async_add_executor_job(
            bridge.get_snapshot, {"aid": 2, "image-width": 300, "image-height": 200}
        )

    with pytest.raises(ValueError):
        assert await hass.async_add_executor_job(
            bridge.get_snapshot, {"aid": 3, "image-width": 300, "image-height": 200}
        )
    with pytest.raises(ValueError):
        assert await hass.async_add_executor_job(
            bridge.get_snapshot, {"aid": 4, "image-width": 300, "image-height": 200}
        )


async def test_camera_stream_source_configured_with_failing_ffmpeg(
    hass, run_driver, events
):
    """Test a camera that can stream with a configured source with ffmpeg failing."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
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
        {CONF_STREAM_SOURCE: "/dev/null", CONF_SUPPORT_AUDIO: True},
    )
    not_camera_acc = Switch(hass, run_driver, "Switch", entity_id, 4, {},)
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)
    bridge.add_accessory(not_camera_acc)

    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_failing_mock_ffmpeg(),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)
        # Calling a second time should not throw
        await _async_stop_all_streams(hass, acc)


async def test_camera_stream_source_found(hass, run_driver, events):
    """Test a camera that can stream and we get the source from the entity."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(hass, run_driver, "Camera", entity_id, 2, {},)
    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)

    await _async_setup_endpoints(hass, acc)

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)


async def test_camera_stream_source_fails(hass, run_driver, events):
    """Test a camera that can stream and we cannot get the source from the entity."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(hass, run_driver, "Camera", entity_id, 2, {},)
    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        side_effect=OSError,
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        await _async_start_streaming(hass, acc)
        await _async_stop_all_streams(hass, acc)


async def test_camera_with_no_stream(hass, run_driver, events):
    """Test a camera that cannot stream."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(hass, camera.DOMAIN, {camera.DOMAIN: {}})

    entity_id = "camera.demo_camera"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(hass, run_driver, "Camera", entity_id, 2, {},)
    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    await _async_start_streaming(hass, acc)
    await _async_stop_all_streams(hass, acc)

    with pytest.raises(HomeAssistantError):
        await hass.async_add_executor_job(
            acc.get_snapshot, {"aid": 2, "image-width": 300, "image-height": 200}
        )


async def test_camera_stream_source_configured_and_copy_codec(hass, run_driver, events):
    """Test a camera that can stream with a configured source."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
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
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_COPY,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    working_ffmpeg = _get_working_mock_ffmpeg()

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=None,
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=working_ffmpeg,
    ):
        await _async_start_streaming(hass, acc)
        await _async_reconfigure_stream(hass, acc, session_info, {})
        await _async_stop_stream(hass, acc, session_info)
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v copy -tune zerolatency -pix_fmt yuv420p -r 30 -b:v 299k "
        "-bufsize 1196k -maxrate 299k -payload_type 99 -ssrc {v_ssrc} -f rtp -srtp_out_suite "
        "AES_CM_128_HMAC_SHA1_80 -srtp_out_params zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246?rtcpport=51246&localrtcpport=51246&pkt_size=1316 -map 0:a:0 "
        "-vn -c:a copy -ac 1 -ar 24k -b:a 24k -bufsize 96k -payload_type 110 -ssrc {a_ssrc} "
        "-f rtp -srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params "
        "shnETgfD+7xUQ8zRdsaytY11wu6CO73IJ+RZVJpU "
        "srtp://192.168.208.5:51108?rtcpport=51108&localrtcpport=51108&pkt_size=188"
    )

    working_ffmpeg.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
    )


async def test_camera_streaming_fails_after_starting_ffmpeg(hass, run_driver, events):
    """Test a camera that can stream with a configured source."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
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
        {
            CONF_STREAM_SOURCE: "/dev/null",
            CONF_SUPPORT_AUDIO: True,
            CONF_VIDEO_CODEC: VIDEO_CODEC_H264_OMX,
            CONF_AUDIO_CODEC: AUDIO_CODEC_COPY,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(acc)

    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    await _async_setup_endpoints(hass, acc)
    session_info = acc.sessions[MOCK_START_STREAM_SESSION_UUID]

    ffmpeg_with_invalid_pid = _get_exits_after_startup_mock_ffmpeg()

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=None,
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=ffmpeg_with_invalid_pid,
    ):
        await _async_start_streaming(hass, acc)
        await _async_reconfigure_stream(hass, acc, session_info, {})
        # Should not throw
        await _async_stop_stream(hass, acc, {"id": "does_not_exist"})
        await _async_stop_all_streams(hass, acc)

    expected_output = (
        "-map 0:v:0 -an -c:v h264_omx -profile:v high -tune zerolatency -pix_fmt yuv420p -r 30 -b:v 299k "
        "-bufsize 1196k -maxrate 299k -payload_type 99 -ssrc {v_ssrc} -f rtp -srtp_out_suite "
        "AES_CM_128_HMAC_SHA1_80 -srtp_out_params zdPmNLWeI86DtLJHvVLI6YPvqhVeeiLsNtrAgbgL "
        "srtp://192.168.208.5:51246?rtcpport=51246&localrtcpport=51246&pkt_size=1316 -map 0:a:0 "
        "-vn -c:a copy -ac 1 -ar 24k -b:a 24k -bufsize 96k -payload_type 110 -ssrc {a_ssrc} "
        "-f rtp -srtp_out_suite AES_CM_128_HMAC_SHA1_80 -srtp_out_params "
        "shnETgfD+7xUQ8zRdsaytY11wu6CO73IJ+RZVJpU "
        "srtp://192.168.208.5:51108?rtcpport=51108&localrtcpport=51108&pkt_size=188"
    )

    ffmpeg_with_invalid_pid.open.assert_called_with(
        cmd=[],
        input_source="-i /dev/null",
        output=expected_output.format(**session_info),
        stdout_pipe=False,
    )
