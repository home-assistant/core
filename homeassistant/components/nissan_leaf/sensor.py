"""Battery Charge and Range Support for the Nissan Leaf."""
import logging

from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.distance import LENGTH_KILOMETERS, LENGTH_MILES
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from . import (
    DATA_BATTERY,
    DATA_CHARGING,
    DATA_LEAF,
    DATA_RANGE_AC,
    DATA_RANGE_AC_OFF,
    LeafEntity,
)

_LOGGER = logging.getLogger(__name__)

ICON_RANGE = "mdi:speedometer"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sensors setup."""
    if discovery_info is None:
        return

    devices = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding sensors for vin=%s", vin)
        devices.append(LeafBatterySensor(datastore))
        devices.append(LeafRangeSensor(datastore, True))
        devices.append(LeafRangeSensor(datastore, False))

    add_devices(devices, True)


class LeafBatterySensor(LeafEntity):
    """Nissan Leaf Battery Sensor."""

    @property
    def name(self):
        """Sensor Name."""
        return f"{self.car.leaf.nickname} Charge"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Battery state percentage."""
        return round(self.car.data[DATA_BATTERY])

    @property
    def unit_of_measurement(self):
        """Battery state measured in percentage."""
        return PERCENTAGE

    @property
    def icon(self):
        """Battery state icon handling."""
        chargestate = self.car.data[DATA_CHARGING]
        return icon_for_battery_level(battery_level=self.state, charging=chargestate)


class LeafRangeSensor(LeafEntity):
    """Nissan Leaf Range Sensor."""

    def __init__(self, car, ac_on):
        """Set up range sensor. Store if AC on."""
        self._ac_on = ac_on
        super().__init__(car)

    @property
    def name(self):
        """Update sensor name depending on AC."""
        if self._ac_on is True:
            return f"{self.car.leaf.nickname} Range (AC)"
        return f"{self.car.leaf.nickname} Range"

    def log_registration(self):
        """Log registration."""
        _LOGGER.debug(
            "Registered LeafRangeSensor integration with Home Assistant for VIN %s",
            self.car.leaf.vin,
        )

    @property
    def state(self):
        """Battery range in miles or kms."""
        if self._ac_on:
            ret = self.car.data[DATA_RANGE_AC]
        else:
            ret = self.car.data[DATA_RANGE_AC_OFF]

        if not self.car.hass.config.units.is_metric or self.car.force_miles:
            ret = IMPERIAL_SYSTEM.length(ret, METRIC_SYSTEM.length_unit)

        return round(ret)

    @property
    def unit_of_measurement(self):
        """Battery range unit."""
        if not self.car.hass.config.units.is_metric or self.car.force_miles:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def icon(self):
        """Nice icon for range."""
        return ICON_RANGE
