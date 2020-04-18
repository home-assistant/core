"""Roomba binary sensor entities."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import roomba_reported_state
from .const import BLID, DOMAIN, ROOMBA_SESSION
from .irobot_base import IRobotEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]
    status = roomba_reported_state(roomba).get("bin", {})
    if "full" in status:
        roomba_vac = RoombaBinStatus(roomba, blid)
        roomba_vac.register_callback()
        async_add_entities([roomba_vac], True)


class RoombaBinStatus(IRobotEntity, BinarySensorDevice):
    """Class to hold Roomba Sensor basic info."""

    ICON = "mdi:delete-variant"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Bin Full"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"bin_{self._blid}"

    @property
    def icon(self):
        """Return the icon of this sensor."""
        return self.ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        bin_status = (
            roomba_reported_state(self.vacuum).get("bin", {}).get("full", False)
        )
        _LOGGER.debug("Update Full Bin status from the vacuum: %s", bin_status)
        return bin_status
