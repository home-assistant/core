"""Laith Switch integration for Home Assistant."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Laith Switch from a config entry."""
    async_add_entities([LaithSwitch()])


class LaithSwitch(SwitchEntity):
    """Representation of the Laith Switch."""

    def __init__(self) -> None:
        """Initialize the switch."""
        self._attr_name = "Laith Switch"
        self._is_on = False
        self._attr_unique_id = "laith_switch_1"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._is_on = False
        self.async_write_ha_state()
