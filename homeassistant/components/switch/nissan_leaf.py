"""
Charge and Climate Control Support for the Nissan Leaf

Documentation pending.
Please refer to the main platform component for configuration details
"""

import logging
from homeassistant.components.nissan_leaf import LeafEntity, DATA_CLIMATE, DATA_CHARGING, DATA_LEAF
from homeassistant.helpers.entity import ToggleEntity


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    _LOGGER.debug("In switch setup platform, discovery_info=%s", discovery_info)


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
    @property
    def name(self):
        return self.car.leaf.nickname + " Climate Control"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafClimateSwitch component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def is_on(self):
        return self.car.data[DATA_CLIMATE] is True

    def turn_on(self, **kwargs):
        if await self.car.async_set_climate(True):
            self.car.data[DATA_CLIMATE] = True

        self._update_callback()

    def turn_off(self, **kwargs):
        if await self.car.async_set_climate(False):
            self.car.data[DATA_CLIMATE] = False

        self._update_callback()

    @property
    def icon(self):
        if self.car.data[DATA_CLIMATE]:
            return 'mdi:fan'
        else:
            return 'mdi:fan-off'


class LeafChargeSwitch(LeafEntity, ToggleEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Charging Status"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafChargeSwitch component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def icon(self):
        if self.car.data[DATA_CHARGING]:
            return 'mdi:flash'
        else:
            return 'mdi:flash-off'

    @property
    def is_on(self):
        return self.car.data[DATA_CHARGING] is True

    def turn_on(self, **kwargs):
        if self.car.start_charging():
            self.car.data[DATA_CHARGING] = True

        self._update_callback()

    def turn_off(self, **kwargs):
        _LOGGER.debug(
            "Cannot turn off Leaf charging -"
            " Nissan does not support that remotely.")
