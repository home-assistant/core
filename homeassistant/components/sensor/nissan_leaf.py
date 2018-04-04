"""
Battery Charge and Range Support for the Nissan Leaf

Documentation pending.
Please refer to the main platform component for configuration details
"""

import logging
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from homeassistant.helpers.icon import icon_for_battery_level
from .. import nissan_leaf as leaf_core

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    if discovery_info is not None:
        return

    _LOGGER.debug("Adding sensors")

    devices = []
    for key, value in hass.data[leaf_core.DATA_LEAF].items():
        devices.append(LeafBatterySensor(value))
        devices.append(LeafRangeSensor(value, True))
        devices.append(LeafRangeSensor(value, False))

    add_devices(devices, True)


class LeafBatterySensor(leaf_core.LeafEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Charge"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafBatterySensor component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def state(self):
        return round(self.car.data[leaf_core.DATA_BATTERY], 0)

    @property
    def unit_of_measurement(self):
        return '%'

    @property
    def icon(self):
        chargeState = self.car.data[leaf_core.DATA_CHARGING]
        return icon_for_battery_level(
            battery_level=self.state,
            charging=chargeState
        )


class LeafRangeSensor(leaf_core.LeafEntity):
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
            "Registered LeafRangeSensor component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def state(self):
        ret = 0

        if self.ac_on is True:
            ret = self.car.data[leaf_core.DATA_RANGE_AC]
        else:
            ret = self.car.data[leaf_core.DATA_RANGE_AC_OFF]

        if (self.car.hass.config.units.is_metric is False or
                self.car.force_miles is True):
            ret = IMPERIAL_SYSTEM.length(ret, METRIC_SYSTEM.length_unit)

        return round(ret, 0)

    @property
    def unit_of_measurement(self):
        if (self.car.hass.config.units.is_metric is False or
                self.car.force_miles is True):
            return "mi"
        else:
            return "km"

    @property
    def icon(self):
        return 'mdi:speedometer'
