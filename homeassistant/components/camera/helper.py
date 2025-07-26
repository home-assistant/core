"""Camera helper functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_CAMERA_PREFS, DATA_COMPONENT

if TYPE_CHECKING:
    from . import Camera
    from .prefs import DynamicStreamSettings


def get_camera_from_entity_id(hass: HomeAssistant, entity_id: str) -> Camera:
    """Get camera component from entity_id."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError("Camera integration not set up")

    if (camera := component.get_entity(entity_id)) is None:
        raise HomeAssistantError("Camera not found")

    if not camera.is_on:
        raise HomeAssistantError("Camera is off")

    return camera


async def get_dynamic_camera_stream_settings(
    hass: HomeAssistant, entity_id: str
) -> DynamicStreamSettings:
    """Get dynamic stream settings for a camera entity."""
    return await hass.data[DATA_CAMERA_PREFS].get_dynamic_stream_settings(entity_id)
