"""Roomba binary sensor entities."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import roomba_reported_state
from .const import BLID, DOMAIN, ROOMBA_SESSION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]
    status = roomba_reported_state(roomba).get("bin", {})
    if "full" in status:
        roomba_vac = RoombaBinStatus(roomba, blid)
        async_add_entities([roomba_vac], True)


class RoombaBinStatus(BinarySensorDevice):
    """Class to hold Roomba Sensor basic info."""

    ICON = "mdi:delete-variant"

    def __init__(self, roomba, blid):
        """Initialize the sensor object."""
        self.vacuum = roomba
        self.vacuum_state = roomba_reported_state(roomba)
        self._blid = blid
        self._name = self.vacuum_state.get("name")
        self._identifier = f"roomba_{self._blid}"
        self._bin_status = None

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
        return self._bin_status

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
        self._bin_status = (
            roomba_reported_state(self.vacuum).get("bin", {}).get("full", False)
        )
        _LOGGER.debug("Update Full Bin status from the vacuum: %s", self._bin_status)
