"""Constants for the Goal Zero Yeti integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)

ATTRIBUTION = "Data provided by Goal Zero"
ATTR_DEFAULT_ENABLED = "default_enabled"

DATA_KEY_COORDINATOR = "coordinator"
DOMAIN = "goalzero"
DEFAULT_NAME = "Yeti"
DATA_KEY_API = "api"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="backlight",
        name="Backlight",
        icon="mdi:clock-digital",
    ),
    BinarySensorEntityDescription(
        key="app_online",
        name="App Online",
        device_class=DEVICE_CLASS_CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="isCharging",
        name="Charging",
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="inputDetected",
        name="Input Detected",
        device_class=DEVICE_CLASS_POWER,
    ),
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="wattsIn",
        name="Watts In",
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ampsIn",
        name="Amps In",
        device_class=DEVICE_CLASS_CURRENT,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wattsOut",
        name="Watts Out",
        device_class=DEVICE_CLASS_POWER,
        unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ampsOut",
        name="Amps Out",
        device_class=DEVICE_CLASS_CURRENT,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="whOut",
        name="WH Out",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="whStored",
        name="WH Stored",
        device_class=DEVICE_CLASS_ENERGY,
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="volts",
        name="Volts",
        device_class=DEVICE_CLASS_VOLTAGE,
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="socPercent",
        name="State of Charge Percent",
        device_class=DEVICE_CLASS_BATTERY,
        unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="timeToEmptyFull",
        name="Time to Empty/Full",
        device_class=TIME_MINUTES,
        unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key="wifiStrength",
        name="Wifi Strength",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
    ),
    SensorEntityDescription(
        key="timestamp",
        name="Total Run Time",
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        unit_of_measurement=TIME_SECONDS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="ssid",
        name="Wi-Fi SSID",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="ipAddr",
        name="IP Address",
        entity_registry_enabled_default=False,
    ),
)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="v12PortStatus",
        name="12V Port Status",
    ),
    SwitchEntityDescription(
        key="usbPortStatus",
        name="USB Port Status",
    ),
    SwitchEntityDescription(
        key="acPortStatus",
        name="AC Port Status",
    ),
)
