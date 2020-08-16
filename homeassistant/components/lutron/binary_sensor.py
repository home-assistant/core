"""Support for Lutron Powr Savr occupancy sensors."""
from pylutron import OccupancyGroup

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron occupancy sensors."""
    if discovery_info is None:
        return
    devs = []
    for (area_name, device) in hass.data[LUTRON_DEVICES]["binary_sensor"]:
        dev = LutronOccupancySensor(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs)


class LutronOccupancySensor(LutronDevice, BinarySensorEntity):
    """Representation of a Lutron Occupancy Group.

    The Lutron integration API reports "occupancy groups" rather than
    individual sensors. If two sensors are in the same room, they're
    reported as a single occupancy group.
    """

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # Error cases will end up treated as unoccupied.
        return self._lutron_device.state == OccupancyGroup.State.OCCUPIED

    @property
    def device_class(self):
        """Return that this is an occupancy sensor."""
        return DEVICE_CLASS_OCCUPANCY

    @property
    def name(self):
        """Return the name of the device."""
        # The default LutronDevice naming would create 'Kitchen Occ Kitchen',
        # but since there can only be one OccupancyGroup per area we go
        # with something shorter.
        return f"{self._area_name} Occupancy"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr["lutron_integration_id"] = self._lutron_device.id
        return attr
