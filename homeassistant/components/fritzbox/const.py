"""Constants for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.binary_sensor import DEVICE_CLASS_WINDOW
from homeassistant.components.fritzbox.model import (
    FritzBinarySensorEntityDescription,
    FritzSensorEntityDescription,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)

ATTR_STATE_BATTERY_LOW: Final = "battery_low"
ATTR_STATE_DEVICE_LOCKED: Final = "device_locked"
ATTR_STATE_HOLIDAY_MODE: Final = "holiday_mode"
ATTR_STATE_LOCKED: Final = "locked"
ATTR_STATE_SUMMER_MODE: Final = "summer_mode"
ATTR_STATE_WINDOW_OPEN: Final = "window_open"

ATTR_TEMPERATURE_UNIT: Final = "temperature_unit"

CONF_CONNECTIONS: Final = "connections"
CONF_COORDINATOR: Final = "coordinator"

DEFAULT_HOST: Final = "fritz.box"
DEFAULT_USERNAME: Final = "admin"

DOMAIN: Final = "fritzbox"

LOGGER: Final[logging.Logger] = logging.getLogger(__package__)

PLATFORMS: Final[list[str]] = ["binary_sensor", "climate", "switch", "sensor"]

BINARY_SENSOR_TYPES: Final[tuple[FritzBinarySensorEntityDescription, ...]] = (
    FritzBinarySensorEntityDescription(
        key="alarm",
        name="Alarm",
        device_class=DEVICE_CLASS_WINDOW,
        suitable=lambda device: device.has_alarm,  # type: ignore[no-any-return]
        is_on=lambda device: device.alert_state,  # type: ignore[no-any-return]
    ),
)

SENSOR_TYPES: Final[tuple[FritzSensorEntityDescription, ...]] = (
    FritzSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        suitable=lambda device: (
            device.has_temperature_sensor and not device.has_thermostat
        ),
        native_value=lambda device: device.temperature,  # type: ignore[no-any-return]
    ),
    FritzSensorEntityDescription(
        key="battery",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        suitable=lambda device: device.battery_level is not None,
        native_value=lambda device: device.battery_level,  # type: ignore[no-any-return]
    ),
    FritzSensorEntityDescription(
        key="power_consumption",
        name="Power Consumption",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        suitable=lambda device: device.has_powermeter,  # type: ignore[no-any-return]
        native_value=lambda device: device.power / 1000 if device.power else 0.0,
    ),
    FritzSensorEntityDescription(
        key="total_energy",
        name="Total Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        suitable=lambda device: device.has_powermeter,  # type: ignore[no-any-return]
        native_value=lambda device: device.energy / 1000 if device.energy else 0.0,
    ),
)
