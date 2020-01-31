"""Tests for the Carson Camera platform."""
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN

from .common import carson_load_fixture, fixture_een_subdomain, setup_platform


async def test_entity_registry(hass, success_requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, CAMERA_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("camera.camera_name_1")
    assert entry.unique_id == "eagleeye_camera_c0"
    entry = entity_registry.async_get("camera.camera_name_2")
    assert entry.unique_id == "eagleeye_camera_c1"


async def test_camera_can_be_updated(hass, success_requests_mock):
    """Tests that the camera returns a binary image."""
    await setup_platform(hass, CAMERA_DOMAIN)

    state = hass.states.get("camera.camera_name_1")
    assert state.attributes.get("friendly_name") == "Camera Name 1"

    een_subdomain = fixture_een_subdomain()
    success_requests_mock.get(
        f"https://{een_subdomain}.eagleeyenetworks.com/g/device/list",
        text=carson_load_fixture("een_device_list_update.json"),
    )

    await hass.services.async_call("carson", "update", {})

    await hass.async_block_till_done()

    state = hass.states.get("camera.camera_name_1")
    assert state.attributes.get("friendly_name") == "Camera Name 1 Updated"
