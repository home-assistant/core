"""Test different accessory types: Camera."""

from uuid import UUID

from asynctest import patch
from pyhap.accessory_driver import AccessoryDriver
import pytest

from homeassistant.components import camera, ffmpeg
from homeassistant.components.homekit.const import (
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
)
from homeassistant.components.homekit.type_cameras import Camera
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


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
    ):
        acc.set_selected_stream_configuration(
            "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
        )
        await acc.stop_stream(session_info)
        await hass.async_block_till_done()

    assert await hass.async_add_executor_job(acc.get_snapshot, 1024)


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
