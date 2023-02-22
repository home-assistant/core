"""Light support for switch entities."""
from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BaseToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Light Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    wrapped_switch = registry.async_get(entity_id)
    device_id = wrapped_switch.device_id if wrapped_switch else None
    entity_category = wrapped_switch.entity_category if wrapped_switch else None

    async_add_entities(
        [
            LightSwitch(
                config_entry.title,
                entity_id,
                config_entry.entry_id,
                device_id,
                entity_category,
            )
        ]
    )


class LightSwitch(BaseToggleEntity, LightEntity):
    """Represents a Switch as a Light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
