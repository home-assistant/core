"""Platform for number integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ELECTRIC_CURRENT_AMPERE, DEVICE_CLASS_CURRENT
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.number import NumberEntity

from .const import DOMAIN
from .common import GoeChargerHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    serial = config_entry.data["serial"]

    async_add_entities([
        GoeChargerNumber(coordinator, config_entry, "Requested current", serial, "requested_current", ELECTRIC_CURRENT_AMPERE, DEVICE_CLASS_CURRENT, "amp")
    ])

class GoeChargerNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry, name: str, serial: str, unique_id: str, unit_of_measurement: str, device_class: str | None, key: str):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._name = name
        self._serial = serial
        self._unique_id = unique_id
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None and self._key in self.coordinator.data

    @property
    def value(self) -> float:
        """Return the state of the sensor."""
        return None if not self.available else self.coordinator.data[self._key]

    @property
    def min_value(self) -> float:
        """Return the state of the sensor."""
        return 6

    @property
    def max_value(self) -> float:
        """Return the state of the sensor."""
        return 32

    @property
    def step(self) -> float:
        """Return the state of the sensor."""
        return 1

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""

        hub = GoeChargerHub(self._config_entry.data["host"])
        await hub.set_data(self.hass, {
            self._key: int(value)
        })

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
