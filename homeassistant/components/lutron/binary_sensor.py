"""Support for Lutron Powr Savr occupancy sensors."""
from __future__ import annotations

from pylutron import OccupancyGroup

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # Error cases will end up treated as unoccupied.
        return self._lutron_device.state == OccupancyGroup.State.OCCUPIED

    @property
    def name(self):
        """Return the name of the device."""
        # The default LutronDevice naming would create 'Kitchen Occ Kitchen',
        # but since there can only be one OccupancyGroup per area we go
        # with something shorter.
        return f"{self._area_name} Occupancy"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
