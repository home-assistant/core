"""Platform for number integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    serial = config_entry.data["serial"]

    async_add_entities([
        GoeChargerBinary(coordinator, "Allow charging", serial, "allow_charging", "alw"),
        GoeChargerBinary(coordinator, "Adapter used", serial, "adapter_used", "adi"),
    ])

class GoeChargerBinary(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, name: str, serial: str, unique_id: str, key: str):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._name = name
        self._serial = serial
        self._unique_id = unique_id
        self._key = key

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return "goe_charger_" + self._serial + "_" + self._unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None and self._key in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return None if not self.available else self.coordinator.data[self._key]

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Get attributes about the device."""
        return {
            "identifiers": {(DOMAIN, self._serial)},
            #"name": self._device.label,
            #"model": self._device.device_type_name,
            #"manufacturer": "Unavailable",
        }
