"""Sensor for checking the battery level of Roomba."""
import logging

<<<<<<< HEAD
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.helpers.entity import Entity
=======
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
>>>>>>> 6f6c670b3b0efdd2e98a3a3ce39b234b1dd4b1d4

from . import roomba_reported_state
from .const import BLID, DOMAIN, ROOMBA_SESSION
from .irobot_base import IRobotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]
    roomba_vac = RoombaBattery(roomba, blid)
    async_add_entities([roomba_vac], True)


class RoombaBattery(IRobotEntity):
    """Class to hold Roomba Sensor basic info."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Battery Level"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"battery_{self._blid}"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return PERCENTAGE

    @property
    def state(self):
        """Return the state of the sensor."""
<<<<<<< HEAD
        return self._battery_level

    @property
    def device_info(self):
        """Return the device info of the vacuum cleaner."""
        return {"identifiers": {(DOMAIN, self._identifier)}, "name": str(self._name)}

    async def async_update(self):
        """Return the update info of the vacuum cleaner."""
        # No data, no update
        if not self.vacuum.master_state:
            _LOGGER.debug("Roomba %s has no data yet. Skip update", self.name)
            return
        self._battery_level = roomba_reported_state(self.vacuum).get("batPct")
        _LOGGER.debug(
            "Update battery level status from the vacuum: %s", self._battery_level
        )
=======
        return roomba_reported_state(self.vacuum).get("batPct")
>>>>>>> 6f6c670b3b0efdd2e98a3a3ce39b234b1dd4b1d4
