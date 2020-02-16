"""Tests for the Abode camera device."""
from unittest.mock import patch

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, CAMERA_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("camera.test_cam")
    assert entry.unique_id == "d0a3a1c316891ceb00c20118aae2a133"


async def test_camera_attributes(hass, requests_mock):
    """Test the camera attributes are correct."""
    await setup_platform(hass, CAMERA_DOMAIN)

    state = hass.states.get("camera.test_cam")
    assert state.state == "idle"


async def test_capture_image(hass, requests_mock):
    """Test the camera capture image service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("abodepy.AbodeCamera.capture") as mock_capture:
        await hass.services.async_call(
            "abode", "capture_image", {"entity_id": "camera.test_cam"}, blocking=True,
        )
        mock_capture.assert_called_once()
