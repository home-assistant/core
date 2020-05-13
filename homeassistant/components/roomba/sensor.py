"""Sensor for checking the battery level of Roomba."""
import logging

from homeassistant.const import DEVICE_CLASS_BATTERY, UNIT_PERCENTAGE

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
        return UNIT_PERCENTAGE

    @property
    def state(self):
        """Return the state of the sensor."""
        return roomba_reported_state(self.vacuum).get("batPct")

    def new_state_filter(self, new_state):
        """Filter the new state."""
        return "batPct" in new_state
