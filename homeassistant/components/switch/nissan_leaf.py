"""
Charge and Climate Control Support for the Nissan Leaf Carwings/Nissan Connect API.

Documentation pending, please refer to the main platform component for configuration details
"""

import logging
from datetime import timedelta

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from .. import nissan_leaf as LeafCore
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
import asyncio


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    for key, value in hass.data[LeafCore.DATA_LEAF].items():
        devices.append(LeafChargeSwitch(value))
        devices.append(LeafClimateSwitch(value))

    add_devices(devices, True)


class LeafClimateSwitch(LeafCore.LeafEntity, ToggleEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Climate Control"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafClimateSwitch component with HASS for VIN " + self.car.leaf.vin)

    @property
    def is_on(self):
        return self.car.data[LeafCore.DATA_CLIMATE] == True

    def turn_on(self, **kwargs):
        if self.car.set_climate(True):
            self.car.data[LeafCore.DATA_CLIMATE] = True

        self._update_callback()

    def turn_off(self, **kwargs):
        if self.car.set_climate(False):
            self.car.data[LeafCore.DATA_CLIMATE] = False

        self._update_callback()


class LeafChargeSwitch(LeafCore.LeafEntity, ToggleEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Charging Status"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafChargeSwitch component with HASS for VIN " + self.car.leaf.vin)

    @property
    def is_on(self):
        return self.car.data[LeafCore.DATA_CHARGING] == True

    def turn_on(self, **kwargs):
        if self.car.start_charging():
            self.car.data[LeafCore.DATA_CHARGING] = True

        self._update_callback()

    def turn_off(self, **kwargs):
        _LOGGER.debug(
            "Cannot turn off Leaf charging - Nissan does not support that remotely.")
