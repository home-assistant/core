"""
Battery Level Sensor for Nissan Leaf
"""

import logging
from datetime import timedelta

from homeassistant.components.sensor import ENTITY_ID_FORMAT
import homeassistant.components.nissan_leaf as LeafCore
from homeassistant.components.nissan_leaf import LeafEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
import asyncio


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    for key, value in hass.data[LeafCore.DATA_LEAF].items():
        devices.append(LeafBatterySensor(value.leaf, value))

    _LOGGER.debug("Adding sensors")

    add_devices(devices, True)

    return True


class LeafBatterySensor(LeafCore.LeafEntity):
    @property
    def name(self):
        return "Leaf Charge %"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafBatterySensor component with HASS for VIN " + self.controller.vin)

    @property
    def state(self):
        return self.data.data[LeafCore.DATA_BATTERY]

    @property
    def unit_of_measurement(self):
        return '%'
