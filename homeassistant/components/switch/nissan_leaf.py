"""
Charge and Climate Control Support for the Nissan Leaf.

Please refer to the main platform component for configuration details
"""

import logging
from homeassistant.components.nissan_leaf import (
    DATA_CHARGING, DATA_CLIMATE, DATA_LEAF, LeafEntity
)
from homeassistant.helpers.entity import ToggleEntity


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Nissan Leaf switch platform setup."""
    _LOGGER.debug("In switch setup platform, discovery_info=%s",
                  discovery_info)

    devices = []
    for key, value in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding switch for item key=%s, value=%s", key, value)
        _LOGGER.debug("Adding LeafChargeSwitch(%s)", value)
        devices.append(LeafChargeSwitch(value))
        _LOGGER.debug("Adding LeafClimateSwitch(%s)", value)
        devices.append(LeafClimateSwitch(value))

    _LOGGER.debug("Calling add_devices for switches")
    add_devices(devices, True)


class LeafClimateSwitch(LeafEntity, ToggleEntity):
    """Nissan Leaf Climate Control switch."""

    @property
    def name(self):
        """Switch name."""
        return self.car.leaf.nickname + " Climate Control"

    def log_registration(self):
        """Log registration."""
        _LOGGER.debug(
            "Registered LeafClimateSwitch component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def is_on(self):
        """Return true if climate control is on."""
        return self.car.data[DATA_CLIMATE] is True

    async def async_turn_on(self, **kwargs):
        """Turn on climate control."""
        if await self.car.async_set_climate(True):
            self.car.data[DATA_CLIMATE] = True

    async def async_turn_off(self, **kwargs):
        """Turn off climate control."""
        if await self.car.async_set_climate(False):
            self.car.data[DATA_CLIMATE] = False

    @property
    def icon(self):
        """Climate control icon."""
        if self.car.data[DATA_CLIMATE]:
            return 'mdi:fan'
        return 'mdi:fan-off'


class LeafChargeSwitch(LeafEntity, ToggleEntity):
    """Nissan Leaf Charging On switch."""

    @property
    def name(self):
        """Switch name."""
        return self.car.leaf.nickname + " Charging Status"

    @property
    def icon(self):
        """Charging switch icon."""
        if self.car.data[DATA_CHARGING]:
            return 'mdi:flash'
        return 'mdi:flash-off'

    @property
    def is_on(self):
        """Return true if charging."""
        return self.car.data[DATA_CHARGING] is True

    async def async_turn_on(self, **kwargs):
        """Start car charging."""
        if await self.car.async_start_charging():
            self.car.data[DATA_CHARGING] = True

    def turn_off(self, **kwargs):
        """Nissan API doesn't allow stopping of charge remotely."""
        _LOGGER.info(
            "Cannot turn off Leaf charging -"
            " Nissan API does not support stopping charge remotely.")
