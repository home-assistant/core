"""Tests for the plant component."""
from homeassistant.components.plant.const import (
    CONF_CHECK_DAYS,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_CONDUCTIVITY,
    CONF_MAX_MOISTURE,
    CONF_MAX_TEMPERATURE,
    CONF_MIN_BATTERY_LEVEL,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_CONDUCTIVITY,
    CONF_MIN_MOISTURE,
    CONF_MIN_TEMPERATURE,
    CONF_PLANT_NAME,
    READING_BATTERY,
    READING_BRIGHTNESS,
    READING_CONDUCTIVITY,
    READING_MOISTURE,
    READING_TEMPERATURE,
)

MOCK_USER_INPUT_USER = {CONF_PLANT_NAME: "Henk"}

MOCK_USER_INPUT_DYNAMIC_SENSORS = [
    {
        "input": {READING_MOISTURE: "sensor.mqtt_plant_moisture"},
        "output": [CONF_MIN_MOISTURE, CONF_MAX_MOISTURE],
    },
    {
        "input": {READING_BATTERY: "sensor.mqtt_plant_moisture"},
        "output": [CONF_MIN_BATTERY_LEVEL],
    },
    {
        "input": {READING_TEMPERATURE: "sensor.mqtt_plant_moisture"},
        "output": [CONF_MIN_TEMPERATURE, CONF_MAX_TEMPERATURE],
    },
    {
        "input": {READING_CONDUCTIVITY: "sensor.mqtt_plant_moisture"},
        "output": [CONF_MIN_CONDUCTIVITY, CONF_MAX_CONDUCTIVITY],
    },
    {
        "input": {READING_BRIGHTNESS: "sensor.mqtt_plant_moisture"},
        "output": [CONF_MIN_BRIGHTNESS, CONF_MAX_BRIGHTNESS, CONF_CHECK_DAYS],
    },
]

MOCK_USER_INPUT_SENSORS = {
    READING_MOISTURE: "sensor.mqtt_plant_moisture",
    READING_BATTERY: "sensor.mqtt_plant_moisture",
    READING_TEMPERATURE: "sensor.mqtt_plant_moisture",
    READING_CONDUCTIVITY: "sensor.mqtt_plant_moisture",
    READING_BRIGHTNESS: "sensor.mqtt_plant_moisture",
}

MOCK_USER_INPUT_LIMITS = {
    CONF_MIN_MOISTURE: 10,
    CONF_MAX_MOISTURE: 70,
    CONF_MIN_BATTERY_LEVEL: 30,
    CONF_MIN_TEMPERATURE: 10,
    CONF_MAX_TEMPERATURE: 24,
    CONF_MIN_CONDUCTIVITY: 100,
    CONF_MAX_CONDUCTIVITY: 2000,
    CONF_MIN_BRIGHTNESS: 100,
    CONF_MAX_BRIGHTNESS: 2000,
    CONF_CHECK_DAYS: 4,
}
