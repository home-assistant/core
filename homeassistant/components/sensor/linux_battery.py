"""
Details about the built-in battery.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.linux_battery/
"""
import logging
import os

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['batinfo==0.4.2']

_LOGGER = logging.getLogger(__name__)

ATTR_NAME = 'name'
ATTR_PATH = 'path'
ATTR_ALARM = 'alarm'
ATTR_CAPACITY = 'capacity'
ATTR_CAPACITY_LEVEL = 'capacity_level'
ATTR_CYCLE_COUNT = 'cycle_count'
ATTR_ENERGY_FULL = 'energy_full'
ATTR_ENERGY_FULL_DESIGN = 'energy_full_design'
ATTR_ENERGY_NOW = 'energy_now'
ATTR_MANUFACTURER = 'manufacturer'
ATTR_MODEL_NAME = 'model_name'
ATTR_POWER_NOW = 'power_now'
ATTR_SERIAL_NUMBER = 'serial_number'
ATTR_STATUS = 'status'
ATTR_VOLTAGE_MIN_DESIGN = 'voltage_min_design'
ATTR_VOLTAGE_NOW = 'voltage_now'

CONF_BATTERY = 'battery'

DEFAULT_BATTERY = 1
DEFAULT_NAME = 'Battery'
DEFAULT_PATH = '/sys/class/power_supply'

ICON = 'mdi:battery'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BATTERY, default=DEFAULT_BATTERY): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Linux Battery sensor."""
    name = config.get(CONF_NAME)
    battery_id = config.get(CONF_BATTERY)

    try:
        os.listdir(os.path.join(DEFAULT_PATH, 'BAT{}'.format(battery_id)))
    except FileNotFoundError:
        _LOGGER.error("No battery found")
        return False

    add_devices([LinuxBatterySensor(name, battery_id)])


class LinuxBatterySensor(Entity):
    """Representation of a Linux Battery sensor."""

    def __init__(self, name, battery_id):
        """Initialize the battery sensor."""
        import batinfo
        self._battery = batinfo.Batteries()

        self._name = name
        self._battery_stat = None
        self._battery_id = battery_id - 1
        self._unit_of_measurement = '%'
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._battery_stat.capacity

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_NAME: self._battery_stat.name,
            ATTR_PATH: self._battery_stat.path,
            ATTR_ALARM: self._battery_stat.alarm,
            ATTR_CAPACITY_LEVEL: self._battery_stat.capacity_level,
            ATTR_CYCLE_COUNT: self._battery_stat.cycle_count,
            ATTR_ENERGY_FULL: self._battery_stat.energy_full,
            ATTR_ENERGY_FULL_DESIGN: self._battery_stat.energy_full_design,
            ATTR_ENERGY_NOW: self._battery_stat.energy_now,
            ATTR_MANUFACTURER: self._battery_stat.manufacturer,
            ATTR_MODEL_NAME: self._battery_stat.model_name,
            ATTR_POWER_NOW: self._battery_stat.power_now,
            ATTR_SERIAL_NUMBER: self._battery_stat.serial_number,
            ATTR_STATUS: self._battery_stat.status,
            ATTR_VOLTAGE_MIN_DESIGN: self._battery_stat.voltage_min_design,
            ATTR_VOLTAGE_NOW: self._battery_stat.voltage_now,
        }

    def update(self):
        """Get the latest data and updates the states."""
        self._battery.update()
        self._battery_stat = self._battery.stat[self._battery_id]
