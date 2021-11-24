"""Button to start charging the Nissan Leaf."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.util.dt import utcnow

from . import DATA_CHARGING, DATA_LEAF, LeafEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up of a Nissan Leaf button."""
    if discovery_info is None:
        return

    devices = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding button for vin=%s", vin)
        devices.append(LeafChargingButton(datastore))
        devices.append(LeafUpdateButton(datastore))

    add_entities(devices, True)


class LeafChargingButton(LeafEntity, ButtonEntity):
    """Charging Button class."""

    _attr_icon = "mdi:power"

    @property
    def name(self):
        """Sensor name."""
        return f"Start {self.car.leaf.nickname} Charging"

    @property
    def available(self):
        """Button availability."""
        return self.car.data[DATA_CHARGING] is not None

    async def async_press(self):
        """Start charging."""
        return await self.car.async_start_charging()


class LeafUpdateButton(LeafEntity, ButtonEntity):
    """Update Button class."""

    _attr_icon = "mdi:refresh"

    @property
    def name(self):
        """Sensor name."""
        return f"Update {self.car.leaf.nickname}"

    @property
    def available(self):
        """Button availability."""
        return self.car.next_update is not None

    async def async_press(self):
        """Start charging."""
        return await self.car.async_refresh_data(utcnow())
