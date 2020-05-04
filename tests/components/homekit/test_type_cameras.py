"""Test different accessory types: Camera."""

from homeassistant.components import camera, ffmpeg
from homeassistant.components.homekit.type_cameras import Camera
from homeassistant.setup import async_setup_component


async def test_camera_stream(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(hass, camera.DOMAIN, {camera.DOMAIN: {}})

    entity_id = "camera.kitchen_door"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Camera(hass, hk_driver, "Camera", entity_id, 2, {})
    await acc.run_handler()

    assert acc.aid == 2
    assert acc.category == 17  # Camera

    stream_service = acc.get_service("CameraRTPStreamManagement")
    endpoints_config_char = stream_service.get_characteristic("SetupEndpoints")
    assert endpoints_config_char.setter_callback
    endpoints_config_char.set_value(
        "ARAzA9UDF8xGmrZykkNqcaL2AgEAAxoBAQACDTE5Mi4xNjguMjA4LjUDAi7IBAKkxwQlAQEAAhDN0+Y0tZ4jzoO0ske9UsjpAw6D76oVXnoi7DbawIG4CwUlAQEAAhCyGcROB8P7vFRDzNF2xrK1Aw6NdcLugju9yCfkWVSaVAYEDoAsAAcEpxV8AA=="
    )
    stream_config_char = stream_service.get_characteristic(
        "SelectedRTPStreamConfiguration"
    )
    assert stream_config_char.setter_callback
    stream_config_char.set_value(
        "ARUCAQEBEDMD1QMXzEaatnKSQ2pxovYCNAEBAAIJAQECAgECAwEAAwsBAgAFAgLQAgMBHgQXAQFjAgQ768/RAwIrAQQEAAAAPwUCYgUDLAEBAwIMAQEBAgEAAwECBAEUAxYBAW4CBCzq28sDAhgABAQAAKBABgENBAEA"
    )
    await hass.async_block_till_done()
