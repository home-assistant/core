"""Platform for number integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .common import GoeChargerHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    serial = config_entry.data["serial"]

    async_add_entities([
        GoeChargerSelect(coordinator, config_entry, "Logic mode", serial, "logic_mode", None, None, "lmo", {
            3: "Default",
            4: "Awattar",
            5: "AutomaticStop"
        }),
        GoeChargerSelect(coordinator, config_entry, "Unlock setting", serial, "unlock_setting", None, None, "ust", {
            0: "Normal",
            1: "AutoUnlock",
            2: "AlwaysLock",
            3: "ForceUnlock"
        }),
        GoeChargerSelect(coordinator, config_entry, "Access control", serial, "access_control", None, None, "acs", {
            0: "Open",
            1: "Wait"
        }),
        GoeChargerSelect(coordinator, config_entry, "Force state", serial, "force_state", None, None, "frc", {
            0: "Neutral",
            1: "Off",
            2: "On"
        }),
        GoeChargerSelect(coordinator, config_entry, "Phase switch mode", serial, "phase_switch_mode", None, None, "psm",
                         {
                             1: "Force_1",
                             2: "Force_3"
                         })
    ])


class GoeChargerSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry, name: str, serial: str,
                 unique_id: str, unit_of_measurement: str, device_class: str | None, key: str, options: dict[int, str]):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._name = name
        self._config_entry = config_entry
        self._serial = serial
        self._unique_id = unique_id
        self._unit_of_measurement = unit_of_measurement
        self._device_class = device_class
        self._key = key
        self._options = options

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
        return (self.coordinator.data is not None and
                self._key in self.coordinator.data and
                self.coordinator.data[self._key] is not None)

    @property
    def current_option(self) -> str | None:
        """The current select option"""
        if not self.available:
            return None

        current_data = self.coordinator.data[self._key]

        if current_data in self._options:
            return self._options[current_data]

        return "Unknown (" + str(current_data) + ")"

    @property
    def options(self) -> list[str]:
        """A list of available options as strings"""
        return list(self._options.values())

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        key_list = list(self._options.keys())
        val_list = list(self._options.values())

        index = val_list.index(option)

        hub = GoeChargerHub(self._config_entry.data["secure"], self._config_entry.data["host"],
                            self._config_entry.data["pathprefix"])
        await hub.set_data(self.hass, {
            self._key: key_list[index]
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
            "identifiers": {(DOMAIN, self._serial)}
        }
