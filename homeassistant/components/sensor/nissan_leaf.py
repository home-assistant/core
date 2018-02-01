"""
Battery Charge and Range Support for the Nissan Leaf Carwings/Nissan Connect API.

Documentation pending, please refer to the main platform component for configuration details
"""

import logging
from .. import nissan_leaf as LeafCore
from ..nissan_leaf import LeafEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    _LOGGER.debug("Adding sensors")

    for key, value in hass.data[LeafCore.DATA_LEAF].items():
        devices.append(LeafBatterySensor(value))
        devices.append(LeafRangeSensor(value, True))
        devices.append(LeafRangeSensor(value, False))

    add_devices(devices, True)

    return True


class LeafBatterySensor(LeafCore.LeafEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Charge"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafBatterySensor component with HASS for VIN " + self.car.leaf.vin)

    @property
    def state(self):
        return round(self.car.data[LeafCore.DATA_BATTERY], 0)

    @property
    def unit_of_measurement(self):
        return '%'


class LeafRangeSensor(LeafCore.LeafEntity):
    def __init__(self, car, ac_on):
        self.ac_on = ac_on
        super().__init__(car)

    @property
    def name(self):
        if self.ac_on is True:
            return self.car.leaf.nickname + " Range (AC)"
        else:
            return self.car.leaf.nickname + " Range"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafRangeSensor component with HASS for VIN " + self.car.leaf.vin)

    @property
    def state(self):
        ret = 0

        if self.ac_on is True:
            ret = self.car.data[LeafCore.DATA_RANGE_AC]
        else:
            ret = self.car.data[LeafCore.DATA_RANGE_AC_OFF]

        if self.car.hass.config.units.is_metric is False or self.car.config[LeafCore.DOMAIN][LeafCore.CONF_FORCE_MILES] is True:
            ret = IMPERIAL_SYSTEM.length(ret, METRIC_SYSTEM.length_unit)

        return round(ret, 0)

    @property
    def unit_of_measurement(self):
        if self.car.hass.config.units.is_metric is False or self.car.config[LeafCore.DOMAIN][LeafCore.CONF_FORCE_MILES] is True:
            return "mi"
        else:
            return "km"
