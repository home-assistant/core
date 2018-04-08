"""
Battery Charge and Range Support for the Nissan Leaf

Documentation pending.
Please refer to the main platform component for configuration details
"""

import logging
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.components.nissan_leaf import DATA_LEAF, LeafEntity, DATA_BATTERY, DATA_CHARGING, DATA_RANGE_AC, DATA_RANGE_AC_OFF

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    _LOGGER.debug("setup_platform nissan_leaf sensors, discovery_info=%s", discovery_info)

    devices = []
    for key, value in hass.data[DATA_LEAF].items():
        _LOGGER.debug("adding sensor for item key=%s, value=%s", key, value)
        _LOGGER.debug("Adding LeafBattery Sensor(value)")
        devices.append(LeafBatterySensor(value))
        _LOGGER.debug("Adding LeafRangeSensor(value, True")
        devices.append(LeafRangeSensor(value, True))
        _LOGGER.debug("Adding LeafRangeSensor(value, False")
        devices.append(LeafRangeSensor(value, False))

    _LOGGER.debug("Actually adding leaf sensor devices")
    add_devices(devices, True)


class LeafBatterySensor(LeafEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Charge"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafBatterySensor component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def state(self):
        return round(self.car.data[DATA_BATTERY], 0)

    @property
    def unit_of_measurement(self):
        return '%'

    @property
    def icon(self):
        chargeState = self.car.data[DATA_CHARGING]
        return icon_for_battery_level(
            battery_level=self.state,
            charging=chargeState
        )


class LeafRangeSensor(LeafEntity):
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
            ret = self.car.data[DATA_RANGE_AC]
        else:
            ret = self.car.data[DATA_RANGE_AC_OFF]

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
