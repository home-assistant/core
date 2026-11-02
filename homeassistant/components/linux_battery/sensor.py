"""Details about the built-in battery."""

from enum import StrEnum
import logging
import os
from typing import Any, override

from batinfo import Batteries
import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_BATTERY = "battery"
CONF_SYSTEM = "system"

DEFAULT_BATTERY = 1
DEFAULT_NAME = "Battery"
DEFAULT_PATH = "/sys/class/power_supply"
DEFAULT_SYSTEM = "linux"

SYSTEMS = ["android", "linux"]


class LinuxBatteryEntityStateAttribute(StrEnum):
    """State attributes for linux_battery entities."""

    ALARM = "alarm"
    CAPACITY_LEVEL = "capacity_level"
    CYCLE_COUNT = "cycle_count"
    ENERGY_FULL = "energy_full"
    ENERGY_FULL_DESIGN = "energy_full_design"
    ENERGY_NOW = "energy_now"
    HEALTH = "health"
    MANUFACTURER = "manufacturer"
    MODEL_NAME = "model_name"
    NAME = "name"
    PATH = "path"
    POWER_NOW = "power_now"
    SERIAL_NUMBER = "serial_number"
    STATUS = "status"
    VOLTAGE_MIN_DESIGN = "voltage_min_design"
    VOLTAGE_NOW = "voltage_now"


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_BATTERY, default=DEFAULT_BATTERY): cv.positive_int,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_SYSTEM, default=DEFAULT_SYSTEM): probatio.In(SYSTEMS),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Linux Battery sensor."""
    name = config.get(CONF_NAME)
    battery_id = config.get(CONF_BATTERY)
    system = config.get(CONF_SYSTEM)

    try:
        if system == "android":
            os.listdir(os.path.join(DEFAULT_PATH, "battery"))
        else:
            os.listdir(os.path.join(DEFAULT_PATH, f"BAT{battery_id}"))
    except FileNotFoundError:
        _LOGGER.error("No battery found")
        return

    add_entities([LinuxBatterySensor(name, battery_id, system)], True)


class LinuxBatterySensor(SensorEntity):
    """Representation of a Linux Battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, name, battery_id, system):
        """Initialize the battery sensor."""
        self._battery = Batteries()

        self._attr_name = name
        self._battery_stat = None
        self._battery_id = battery_id - 1
        self._system = system

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        if self._system == "android":
            return {
                LinuxBatteryEntityStateAttribute.NAME: self._battery_stat.name,
                LinuxBatteryEntityStateAttribute.PATH: self._battery_stat.path,
                LinuxBatteryEntityStateAttribute.HEALTH: self._battery_stat.health,
                LinuxBatteryEntityStateAttribute.STATUS: self._battery_stat.status,
            }
        return {
            LinuxBatteryEntityStateAttribute.NAME: self._battery_stat.name,
            LinuxBatteryEntityStateAttribute.PATH: self._battery_stat.path,
            LinuxBatteryEntityStateAttribute.ALARM: self._battery_stat.alarm,
            LinuxBatteryEntityStateAttribute.CAPACITY_LEVEL: self._battery_stat.capacity_level,
            LinuxBatteryEntityStateAttribute.CYCLE_COUNT: self._battery_stat.cycle_count,
            LinuxBatteryEntityStateAttribute.ENERGY_FULL: self._battery_stat.energy_full,
            LinuxBatteryEntityStateAttribute.ENERGY_FULL_DESIGN: self._battery_stat.energy_full_design,
            LinuxBatteryEntityStateAttribute.ENERGY_NOW: self._battery_stat.energy_now,
            LinuxBatteryEntityStateAttribute.MANUFACTURER: self._battery_stat.manufacturer,
            LinuxBatteryEntityStateAttribute.MODEL_NAME: self._battery_stat.model_name,
            LinuxBatteryEntityStateAttribute.POWER_NOW: self._battery_stat.power_now,
            LinuxBatteryEntityStateAttribute.SERIAL_NUMBER: self._battery_stat.serial_number,
            LinuxBatteryEntityStateAttribute.STATUS: self._battery_stat.status,
            LinuxBatteryEntityStateAttribute.VOLTAGE_MIN_DESIGN: self._battery_stat.voltage_min_design,
            LinuxBatteryEntityStateAttribute.VOLTAGE_NOW: self._battery_stat.voltage_now,
        }

    def update(self) -> None:
        """Get the latest data and updates the states."""
        self._battery.update()
        self._battery_stat = self._battery.stat[self._battery_id]
        self._attr_native_value = self._battery_stat.capacity
