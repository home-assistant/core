"""Test different accessory types: Camera."""

from uuid import UUID

from pyhap.accessory_driver import AccessoryDriver
import pytest

from homeassistant.components import camera, ffmpeg
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
)
from homeassistant.components.homekit.type_cameras import Camera
from homeassistant.components.homekit.type_switches import Switch
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, MagicMock, patch


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

    stream_service = acc.get_service("CameraRTPStreamManagement")
    endpoints_config_char = stream_service.get_characteristic("SetupEndpoints")
    assert endpoints_config_char.setter_callback
    stream_config_char = stream_service.get_characteristic(
        "SelectedRTPStreamConfiguration"
    )
    assert stream_config_char.setter_callback
    acc.set_endpoints(
        "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
    )

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value=None,
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await hass.async_block_till_done()

    session_info = {
        "id": "mock",
        "v_srtp_key": "key",
        "a_srtp_key": "key",
        "v_port": "0",
        "a_port": "0",
        "address": "0.0.0.0",
    }
    acc.sessions[UUID("3303d503-17cc-469a-b672-92436a71a2f6")] = session_info

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await acc.stop_stream(session_info)
        # Calling a second time should not throw
        await acc.stop_stream(session_info)
        await hass.async_block_till_done()

    assert await hass.async_add_executor_job(acc.get_snapshot, 1024)

    # Verify the bridge only forwards get_snapshot for
    # cameras and valid accessory ids
    assert await hass.async_add_executor_job(bridge.get_snapshot, {"aid": 2})
    with pytest.raises(ValueError):
        assert await hass.async_add_executor_job(bridge.get_snapshot, {"aid": 3})
    with pytest.raises(ValueError):
        assert await hass.async_add_executor_job(bridge.get_snapshot, {"aid": 4})


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

    stream_service = acc.get_service("CameraRTPStreamManagement")
    endpoints_config_char = stream_service.get_characteristic("SetupEndpoints")
    assert endpoints_config_char.setter_callback
    stream_config_char = stream_service.get_characteristic(
        "SelectedRTPStreamConfiguration"
    )
    assert stream_config_char.setter_callback
    acc.set_endpoints(
        "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
    )

    session_info = {
        "id": "mock",
        "v_srtp_key": "key",
        "a_srtp_key": "key",
        "v_port": "0",
        "a_port": "0",
        "address": "0.0.0.0",
    }
    acc.sessions[UUID("3303d503-17cc-469a-b672-92436a71a2f6")] = session_info

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_failing_mock_ffmpeg(),
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await acc.stop_stream(session_info)
        # Calling a second time should not throw
        await acc.stop_stream(session_info)
        await hass.async_block_till_done()


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

    stream_service = acc.get_service("CameraRTPStreamManagement")
    endpoints_config_char = stream_service.get_characteristic("SetupEndpoints")
    assert endpoints_config_char.setter_callback
    stream_config_char = stream_service.get_characteristic(
        "SelectedRTPStreamConfiguration"
    )
    assert stream_config_char.setter_callback
    acc.set_endpoints(
        "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
    )

    session_info = {
        "id": "mock",
        "v_srtp_key": "key",
        "a_srtp_key": "key",
        "v_port": "0",
        "a_port": "0",
        "address": "0.0.0.0",
    }
    acc.sessions[UUID("3303d503-17cc-469a-b672-92436a71a2f6")] = session_info

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await acc.stop_stream(session_info)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        return_value="rtsp://example.local",
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await acc.stop_stream(session_info)
        await hass.async_block_till_done()


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

    stream_service = acc.get_service("CameraRTPStreamManagement")
    endpoints_config_char = stream_service.get_characteristic("SetupEndpoints")
    assert endpoints_config_char.setter_callback
    stream_config_char = stream_service.get_characteristic(
        "SelectedRTPStreamConfiguration"
    )
    assert stream_config_char.setter_callback
    acc.set_endpoints(
        "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
    )

    session_info = {
        "id": "mock",
        "v_srtp_key": "key",
        "a_srtp_key": "key",
        "v_port": "0",
        "a_port": "0",
        "address": "0.0.0.0",
    }
    acc.sessions[UUID("3303d503-17cc-469a-b672-92436a71a2f6")] = session_info

    with patch(
        "homeassistant.components.demo.camera.DemoCamera.stream_source",
        side_effect=OSError,
    ), patch(
        "homeassistant.components.homekit.type_cameras.HAFFmpeg",
        return_value=_get_working_mock_ffmpeg(),
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await acc.stop_stream(session_info)
        await hass.async_block_till_done()


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

    acc.set_endpoints(
        "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
    )
    acc.set_selected_stream_configuration(
        "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
    )
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.async_add_executor_job(acc.get_snapshot, 1024)
