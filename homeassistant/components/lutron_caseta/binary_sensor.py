"""Support for Lutron Caseta Occupancy/Vacancy Sensors."""
from pylutron_caseta import OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)

from . import DOMAIN as CASETA_DOMAIN, LutronCasetaDevice
from .const import BRIDGE_DEVICE, BRIDGE_LEAP


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta binary_sensor platform.

    Adds occupancy groups from the Caseta bridge associated with the
    config_entry as binary_sensor entities.
    """

    entities = []
    data = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data[BRIDGE_LEAP]
    bridge_device = data[BRIDGE_DEVICE]
    occupancy_groups = bridge.occupancy_groups

    for occupancy_group in occupancy_groups.values():
        entity = LutronOccupancySensor(occupancy_group, bridge, bridge_device)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronOccupancySensor(LutronCasetaDevice, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    @property
    def device_class(self):
        """Flag supported features."""
        return DEVICE_CLASS_OCCUPANCY

    @property
    def is_on(self):
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self.device_id}"

    @property
    def device_info(self):
        """Return the device info.

        Sensor entities are aggregated from one or more physical
        sensors by each room. Therefore, there shouldn't be devices
        related to any sensor entities.
        """
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}
