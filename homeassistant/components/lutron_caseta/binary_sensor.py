"""Support for Lutron Caseta Occupancy/Vacancy Sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    DOMAIN,
    BinarySensorDevice,
)
from pylutron_caseta import (OCCUPANCY_GROUP_OCCUPIED,
                             OCCUPANCY_GROUP_UNOCCUPIED)
from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    occupancy_groups = bridge.occupancy_groups
    for occupancy_group in occupancy_groups.values():
        dev = LutronOccupancySensor(occupancy_group, bridge)
        devs.append(dev)

    async_add_entities(devs, True)


class LutronOccupancySensor(LutronCasetaDevice, BinarySensorDevice):
    """Representation of a Lutron occupancy group."""

    @property
    def device_class(self):
        """Flag supported features."""
        return DEVICE_CLASS_OCCUPANCY

    @property
    def is_on(self):
        """Return the brightness of the light."""
        return self._device['status'] == OCCUPANCY_GROUP_OCCUPIED

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_schedule_update_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def serial(self):
        """Return a unique identifier."""
        return f"caseta_occupancygroup_{self.device_id}"

    @property
    def model(self):
        """Return a model number"""
        return "PD-OSENS-WH"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"Device ID": self.device_id}
