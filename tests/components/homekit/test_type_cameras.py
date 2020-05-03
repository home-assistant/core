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
