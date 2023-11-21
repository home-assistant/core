"""Support for DROP selects."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_COORDINATOR,
    CONF_DEVICE_TYPE,
    DEV_HUB,
    DOMAIN as DROP_DOMAIN,
    PROTECT_MODE_OPTIONS,
)
from .entity import DROP_Entity

_LOGGER = logging.getLogger(__name__)

FLOOD_ICON = "mdi:home-flood"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP select platform."""
    _LOGGER.debug(
        "Set up select for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )
    entities = []
    if config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
        entities.extend(
            [
                DROP_ProtectModeSelect(
                    hass.data[DROP_DOMAIN][config_entry.entry_id][CONF_COORDINATOR]
                ),
            ]
        )
    async_add_entities(entities)


class DROP_ProtectModeSelect(DROP_Entity, SelectEntity):
    """Representation of a DROP Protect Mode state."""

    _attr_icon = FLOOD_ICON
    _attr_translation_key = "protect_mode"
    _attr_options = PROTECT_MODE_OPTIONS
    _attr_current_option: str | None = None

    def __init__(self, device) -> None:
        """Initialize the protect mode select."""
        super().__init__("protect_mode", device)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._device.protect_mode is None:
            return None
        return self._device.protect_mode

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        if option in PROTECT_MODE_OPTIONS:
            await self._device.set_protect_mode(option)
            self._attr_current_option = option
            self.async_write_ha_state()
