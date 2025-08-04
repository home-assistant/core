"""Support for Lutron Variables."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .aiolip import LutronController, Sysvar
from .entity import LutronVariable

_LOGGER = logging.getLogger(__name__)

VALUE_TO_LABEL = {
    0: "Value 0",
    1: "Value 1",
    2: "Value 2",
    3: "Value 3",
    10: "High",
}

LABEL_TO_VALUE = {v: k for k, v in VALUE_TO_LABEL.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron sensor platform.

    Adds variables to the controller as sensor entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            LutronVariableSelect(device, entry_data.controller)
            for device in entry_data.variables
        ],
        True,
    )


class LutronVariableSelect(LutronVariable, SelectEntity):
    """Representation of a Lutron Variable."""

    def __init__(
        self,
        lutron_device: Sysvar,
        controller: LutronController,
    ) -> None:
        """Initialize the occupancy sensor."""
        super().__init__(lutron_device, controller)
        self._attr_options = list(LABEL_TO_VALUE.keys())
        self._current_value = 0

    @property
    def current_option(self):
        """Return the current option."""
        return VALUE_TO_LABEL.get(self._current_value, "Off")

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        new_value = LABEL_TO_VALUE[option]
        await self._execute_device_command(self._lutron_device.set_state, new_value)

    async def _request_state(self):
        await self._execute_device_command(self._lutron_device.get_state)

    def _update_callback(self, value: int):
        """Handle state update."""
        self._current_value = value
        self.async_write_ha_state()
