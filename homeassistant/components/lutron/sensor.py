"""Support for Lutron Variables."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronController, LutronData
from .entity import LutronVariable
from .lutron_db import Sysvar

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron sensor platform.

    Adds variable from the Main Repeater associated with the
    config_entry as sensor entities.
    DISABLED using LutronVariableSelect instead.
    """

    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    entry_data.variables = []

    async_add_entities(
        [
            LutronVariableSensor("", device_name, device, entry_data.controller)
            for device_name, device in entry_data.variables
        ],
        True,
    )


class LutronVariableSensor(LutronVariable, SensorEntity):
    """Representation of a Lutron Variable. This only gets updates.

    Not used. Lutron variables are represented by LutronVariableSelect.
    """

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        area_name: str,
        device_name: str,
        lutron_device: Sysvar,
        controller: LutronController,
    ) -> None:
        """Initialize the occupancy sensor."""
        super().__init__(area_name, lutron_device.name, lutron_device, controller)

    async def _request_state(self):
        await self._controller.sysvar_get_state(self._lutron_device.id)

    def _update_callback(self, value: int):
        """Set variable state."""
        self._attr_native_value = value
        self.async_write_ha_state()
