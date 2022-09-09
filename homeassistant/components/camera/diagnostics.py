"""Diagnostics for camera."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import _get_camera_from_entity_id
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    diagnostics = {}
    for entity in entities:
        if entity.domain != DOMAIN:
            continue
        try:
            camera = _get_camera_from_entity_id(hass, entity.entity_id)
        except HomeAssistantError:
            continue
        diagnostics[entity.entity_id] = (
            camera.stream.get_diagnostics() if camera.stream else {}
        )
    return diagnostics
