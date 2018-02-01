"""
Plugged In Status Support for the Nissan Leaf Carwings/Nissan Connect API.

Documentation pending, please refer to the main platform API f
"""

import logging
from datetime import timedelta

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from .. import nissan_leaf as LeafCore
from ..nissan_leaf import LeafEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
import asyncio
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    _LOGGER.debug("Adding sensors")

    for key, value in hass.data[LeafCore.DATA_LEAF].items():
        devices.append(LeafPluggedInSensor(value))

    add_devices(devices, True)

    return True


class LeafPluggedInSensor(LeafCore.LeafEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Plug Status"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafPluggedInSensor component with HASS for VIN " + self.car.leaf.vin)

    @property
    def state(self):
        return self.car.data[LeafCore.DATA_PLUGGED_IN]
