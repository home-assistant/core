"""Constants for the Intellifire integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorEntityDescription, SensorStateClass
from homeassistant.const import TIME_MINUTES, TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE

DOMAIN = "intellifire"
POWER = "on_off"
TIMER = "timer_on"
HOT = "is_hot"
THERMOSTAT = "thermostat_on"
FAN = "fan_on"
LIGHT = "light_on"
FAN_SPEED = "fan_speed"
FLAME_HEIGHT = "flame_height"
PILOT = "pilot_light_on"
TIMER_TIME = "timer_remaining"
TEMP = "temperature"
THERMOSTAT_TARGET = "Target Temp"


INTELLIFIRE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=FLAME_HEIGHT,
        icon="mdi:fire-circle",
        name="Flame Height",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TEMP,
        icon="mdi:car-brake-temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    SensorEntityDescription(
        key=THERMOSTAT_TARGET,
        icon="mdi:thermometer-lines",
        name="Target Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    # SensorEntityDescription(
    #     key=ATTR_API_PM25,
    #     icon="mdi:blur",
    #     name=ATTR_API_PM25,
    #     native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    #     state_class=SensorStateClass.MEASUREMENT,
    # ),
    SensorEntityDescription(
        key=FAN_SPEED,
        icon="mdi:fan",
        name="Fan Speed",
        # native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TIMER_TIME,
        icon="mdi:timer-sand",
        name="Timer Time Remaining",
        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


INTELLIFIRE_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=POWER,  # This is the sensor name
        name="Power",  # This is the human readable name
        icon="mdi:power",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key=TIMER, name="Timer On", icon="mdi:camera-timer", device_class=None
    ),
    BinarySensorEntityDescription(
        key=PILOT, name="Pilot Light On", icon="mdi:fire-alert", device_class=None
    ),
    # BinarySensorEntityDescription(
    #     key=HOT,
    #     name="Is Hot",
    #     icon="mdi:fire",
    #     # device_class=BinarySensorDeviceClass.HEAT
    # ),
    BinarySensorEntityDescription(
        key=THERMOSTAT,
        name="Thermostat On",
        icon="mdi:home-thermometer-outline",
        device_class=None,
    ),
)
