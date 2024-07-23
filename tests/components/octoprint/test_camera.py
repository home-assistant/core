"""The tests for Octoptint camera module."""

from unittest.mock import patch

from pyoctoprintapi import WebcamSettings

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_camera(hass: HomeAssistant) -> None:
    """Test the underlying camera."""
    with patch(
        "pyoctoprintapi.OctoprintClient.get_webcam_info",
        return_value=WebcamSettings(
            base_url="http://fake-octoprint/",
            raw={
                "streamUrl": "/webcam/?action=stream",
                "snapshotUrl": "http://127.0.0.1:8080/?action=snapshot",
                "webcamEnabled": True,
            },
        ),
    ):
        await init_integration(hass, CAMERA_DOMAIN)

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("camera.octoprint_camera")
    assert entry is not None
    assert entry.unique_id == "uuid"


async def test_camera_disabled(hass: HomeAssistant) -> None:
    """Test that the camera does not load if there is not one configured."""
    with patch(
        "pyoctoprintapi.OctoprintClient.get_webcam_info",
        return_value=WebcamSettings(
            base_url="http://fake-octoprint/",
            raw={
                "streamUrl": "/webcam/?action=stream",
                "snapshotUrl": "http://127.0.0.1:8080/?action=snapshot",
                "webcamEnabled": False,
            },
        ),
    ):
        await init_integration(hass, CAMERA_DOMAIN)

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("camera.octoprint_camera")
    assert entry is None


async def test_no_supported_camera(hass: HomeAssistant) -> None:
    """Test that the camera does not load if there is not one configured."""
    with patch(
        "pyoctoprintapi.OctoprintClient.get_webcam_info",
        return_value=None,
    ):
        await init_integration(hass, CAMERA_DOMAIN)

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("camera.octoprint_camera")
    assert entry is None
