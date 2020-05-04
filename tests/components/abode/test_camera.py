"""Tests for the Abode camera device."""
from homeassistant.components.abode.const import DOMAIN as ABODE_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_IDLE

from .common import setup_platform

from tests.async_mock import patch


async def test_entity_registry(hass):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, CAMERA_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("camera.test_cam")
    assert entry.unique_id == "d0a3a1c316891ceb00c20118aae2a133"


async def test_attributes(hass):
    """Test the camera attributes are correct."""
    await setup_platform(hass, CAMERA_DOMAIN)

    state = hass.states.get("camera.test_cam")
    assert state.state == STATE_IDLE


async def test_capture_image(hass):
    """Test the camera capture image service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("abodepy.AbodeCamera.capture") as mock_capture:
        await hass.services.async_call(
            ABODE_DOMAIN,
            "capture_image",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once()
