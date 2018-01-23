"""
Charge and Climate Switch for Nissan Leaf
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
        return "Leaf Climate Control"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafClimateSwitch component with HASS for VIN " + self.car.leaf.vin)

    @property
    def is_on(self):
        return self.car.data[LeafCore.DATA_CLIMATE] == True

    def turn_on(self, **kwargs):
        # if self.controller.set_climate(True):
            # self.data[LeafCore.DATA_CLIMATE] = True
        _LOGGER.info("Climate Control is not implemented yet.")

    def turn_off(self, **kwargs):
        _LOGGER.info("Climate Control is not implemented yet.")
        # if self.controller.set_climate(False):
        # self.data[LeafCore.DATA_CLIMATE] = False


class LeafChargeSwitch(LeafCore.LeafEntity, ToggleEntity):
    @property
    def name(self):
        return "Leaf Charging Status"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafChargeSwitch component with HASS for VIN " + self.car.leaf.vin)

    @property
    def is_on(self):
        return self.car.data[LeafCore.DATA_CHARGING] == True

    def turn_on(self, entity_id):
        _LOGGER.info("Charging is not implemented yet.")
        # if self.controller.start_charging():
        # self.data[LeafCore.DATA_CHARGING] = True

    def turn_off(self, entity_id):
        _LOGGER.debug(
            "Cannot turn off Leaf charging - Nissan does not support that remotely.")
