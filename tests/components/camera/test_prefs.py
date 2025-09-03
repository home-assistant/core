"""Test camera helper functions."""

import pytest

from homeassistant.components.camera.const import DATA_CAMERA_PREFS
from homeassistant.components.camera.prefs import (
    CameraPreferences,
    DynamicStreamSettings,
    get_dynamic_camera_stream_settings,
)
from homeassistant.components.stream import Orientation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_get_dynamic_camera_stream_settings_missing_prefs(
    hass: HomeAssistant,
) -> None:
    """Test get_dynamic_camera_stream_settings when camera prefs are not set up."""
    with pytest.raises(HomeAssistantError, match="Camera integration not set up"):
        await get_dynamic_camera_stream_settings(hass, "camera.test")


async def test_get_dynamic_camera_stream_settings_success(hass: HomeAssistant) -> None:
    """Test successful retrieval of dynamic camera stream settings."""
    # Set up camera preferences
    prefs = CameraPreferences(hass)
    await prefs.async_load()
    hass.data[DATA_CAMERA_PREFS] = prefs

    # Test with default settings
    settings = await get_dynamic_camera_stream_settings(hass, "camera.test")
    assert settings.orientation == Orientation.NO_TRANSFORM
    assert settings.preload_stream is False


async def test_get_dynamic_camera_stream_settings_with_custom_orientation(
    hass: HomeAssistant,
) -> None:
    """Test get_dynamic_camera_stream_settings with custom orientation set."""
    # Set up camera preferences
    prefs = CameraPreferences(hass)
    await prefs.async_load()
    hass.data[DATA_CAMERA_PREFS] = prefs

    # Set custom orientation - this requires entity registry
    # For this test, we'll directly manipulate the internal state
    # since entity registry setup is complex for a unit test
    test_settings = DynamicStreamSettings(
        orientation=Orientation.ROTATE_LEFT, preload_stream=False
    )
    prefs._dynamic_stream_settings_by_entity_id["camera.test"] = test_settings

    settings = await get_dynamic_camera_stream_settings(hass, "camera.test")
    assert settings.orientation == Orientation.ROTATE_LEFT
    assert settings.preload_stream is False


async def test_get_dynamic_camera_stream_settings_with_preload_stream(
    hass: HomeAssistant,
) -> None:
    """Test get_dynamic_camera_stream_settings with preload stream enabled."""
    # Set up camera preferences
    prefs = CameraPreferences(hass)
    await prefs.async_load()
    hass.data[DATA_CAMERA_PREFS] = prefs

    # Set preload stream by directly setting the dynamic stream settings
    test_settings = DynamicStreamSettings(
        orientation=Orientation.NO_TRANSFORM, preload_stream=True
    )
    prefs._dynamic_stream_settings_by_entity_id["camera.test"] = test_settings

    settings = await get_dynamic_camera_stream_settings(hass, "camera.test")
    assert settings.orientation == Orientation.NO_TRANSFORM
    assert settings.preload_stream is True
