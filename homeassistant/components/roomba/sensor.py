"""Sensor for checking the battery level of Roomba."""
import logging

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the iRobot Roomba vacuum cleaner."""
    roomba = hass.data[DOMAIN]["roomba"]
    roomba_vac = RoombaBattery(roomba)
    async_add_entities([roomba_vac], True)


class RoombaBattery(Entity):
    """Class to hold Roomba Sensor basic info."""

    def __init__(self, roomba):
        """Initialize the sensor object."""
        self.vacuum = roomba
        self.vacuum_state = self.vacuum.master_state.get("state", {}).get(
            "reported", {}
        )
        self._mac = self.vacuum_state.get("mac")
        self._name = self.vacuum_state.get("name")
        self._identifier = f"roomba_{self._mac}"
        self._battery_level = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} battery level"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"battery_{self._mac}"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return "%"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._battery_level

    @property
    def device_info(self):
        """Return the device info of the vacuum cleaner."""
        return {
            "identifiers": {(DOMAIN, self._identifier)},
            "name": str(self._name),
        }

    async def async_update(self):
        """Return the update info of the vacuum cleaner."""
        # No data, no update
        if not self.vacuum.master_state:
            _LOGGER.debug("Roomba %s has no data yet. Skip update", self.name)
            return
        self._battery_level = (
            self.vacuum.master_state.get("state", {}).get("reported", {}).get("batPct")
        )
        _LOGGER.debug(
            "Update battery level status from the vacuum: %s", self._battery_level
        )
