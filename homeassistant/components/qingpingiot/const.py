"""Constants for the Qingping IoT integration."""

from enum import StrEnum
from typing import Final, TypedDict

from homeassistant.const import Platform

# Integration
DOMAIN: Final = "qingpingiot"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
]

# Config keys
CONF_MAC: Final = "mac"
CONF_NAME: Final = "name"
CONF_MODEL: Final = "model"
CONF_DEVICE: Final = "device"

# MQTT
MQTT_TOPIC_PREFIX: Final = "qingping"

# Sensor types
SENSOR_BATTERY: Final = "battery"
SENSOR_TEMPERATURE: Final = "temperature"
SENSOR_HUMIDITY: Final = "humidity"
SENSOR_CO2: Final = "co2"
SENSOR_PM25: Final = "pm25"
SENSOR_PM10: Final = "pm10"
SENSOR_TVOC: Final = "tvoc"
SENSOR_ETVOC: Final = "tvoc_index"
SENSOR_NOISE: Final = "noise"
SENSOR_PRESSURE: Final = "pressure"
SENSOR_LIGHT: Final = "light"
SENSOR_SIGNAL_STRENGTH: Final = "signal_strength"


class Capability(StrEnum):
    """Device capability identifiers."""

    BATTERY = "battery"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    PM25 = "pm25"
    PM10 = "pm10"
    TVOC = "tvoc"
    ETVOC = "tvoc_index"
    NOISE = "noise"
    PRESSURE = "pressure"
    LIGHT = "light"
    SIGNAL_STRENGTH = "signal_strength"
    # Control capabilities
    CO2_ASC = "co2_asc"
    CO2_CALIBRATION = "co2_calibration"
    LED_INDICATOR = "led_indicator"
    TEMPERATURE_UNIT = "temperature_unit"


class Protocol(StrEnum):
    """Communication protocol types."""

    BLE = "ble"
    MQTT = "mqtt"


PERCENTAGE: Final = "%"
PPM: Final = "ppm"
PPB: Final = "ppb"
INDEX: Final = "VOC index"
CONCENTRATION: Final = "µg/m³"
DB: Final = "dB"
MG_PER_M3: Final = "mg/m³"

# eTVOC unit: internal key → display unit
ETVOC_UNIT_DISPLAY_MAP: Final = {"index": INDEX, "ppb": PPB, "mg_m3": MG_PER_M3}

# Report modes (TLV devices)
CONF_REPORT_MODE: Final = "report_mode"

# VOC unit config
CONF_TVOC_UNIT: Final = "tvoc_unit"
CONF_ETVOC_UNIT: Final = "etvoc_unit"

# Temperature unit config (TLV)
CONF_TEMPERATURE_UNIT: Final = "temperature_unit"

# Online/offline timeouts (seconds)
OFFLINE_TIMEOUT_REALTIME: Final = 900

# TLV intervals
CONF_REPORT_INTERVAL: Final = "report_interval"  # Minutes (KEY 0x04)
CONF_SAMPLE_INTERVAL: Final = "sample_interval"  # Seconds (KEY 0x05)
CONF_UPDATE_INTERVAL: Final = "update_interval"  # Seconds (JSON devices)

DEFAULT_SAMPLE_INTERVAL: Final = 60  # seconds
DEFAULT_UPDATE_INTERVAL: Final = 60  # seconds

# Offsets
CONF_TEMPERATURE_OFFSET: Final = "temperature_offset"
CONF_HUMIDITY_OFFSET: Final = "humidity_offset"
CONF_CO2_OFFSET: Final = "co2_offset"
CONF_PM25_OFFSET: Final = "pm25_offset"
CONF_PM10_OFFSET: Final = "pm10_offset"
CONF_NOISE_OFFSET: Final = "noise_offset"
CONF_TVOC_OFFSET: Final = "tvoc_offset"
CONF_TVOC_INDEX_OFFSET: Final = "tvoc_index_offset"
CONF_PRESSURE_OFFSET: Final = "pressure_offset"

DEFAULT_OFFSET: Final = 0


# Report interval config per model
class ReportIntervalConfig(TypedDict):
    """Report interval configuration for a device model."""

    default: int
    min: int
    unit: str  # "min" or "s"


# Device model definitions
class DeviceModelInfo(TypedDict):
    """Device model metadata."""

    name: str
    protocols: list[str]
    capabilities: list[Capability]
    report_interval: ReportIntervalConfig


DEVICE_MODELS: dict[str, DeviceModelInfo] = {
    # -- Qingping Indoor Environment Monitor --
    "cgr1w": {
        "name": "Qingping Indoor Environment Monitor",
        "protocols": [Protocol.MQTT],
        "capabilities": [
            Capability.TEMPERATURE,
            Capability.HUMIDITY,
            Capability.CO2,
            Capability.PM25,
            Capability.PM10,
            Capability.NOISE,
            Capability.LIGHT,
            Capability.SIGNAL_STRENGTH,
            Capability.CO2_ASC,
            Capability.CO2_CALIBRATION,
            Capability.LED_INDICATOR,
            Capability.TEMPERATURE_UNIT,
        ],
        "report_interval": {"default": 60, "min": 1, "unit": "min"},
    },
    # -- Qingping Multi-Role Monitor Pro --
    "cgf2w": {
        "name": "Qingping Multi-Role Monitor Pro",
        "protocols": [Protocol.MQTT],
        "capabilities": [
            Capability.TEMPERATURE,
            Capability.HUMIDITY,
            Capability.TEMPERATURE_UNIT,
        ],
        "report_interval": {"default": 60, "min": 10, "unit": "min"},
    },
    # Qingping Air Monitor
    "cgs2": {
        "name": "Qingping Air Monitor",
        "protocols": [Protocol.MQTT],
        "capabilities": [
            Capability.TEMPERATURE,
            Capability.HUMIDITY,
            Capability.CO2,
            Capability.PM25,
            Capability.PM10,
            Capability.NOISE,
            Capability.BATTERY,
            Capability.ETVOC,
        ],
        "report_interval": {"default": 900, "min": 10, "unit": "s"},
    },
    # Qingping Air Monitor Lite
    "cgdn1": {
        "name": "Qingping Air Monitor Lite",
        "protocols": [Protocol.MQTT],
        "capabilities": [
            Capability.TEMPERATURE,
            Capability.HUMIDITY,
            Capability.CO2,
            Capability.PM25,
            Capability.PM10,
            Capability.BATTERY,
            Capability.CO2_ASC,
            Capability.CO2_CALIBRATION,
            Capability.TEMPERATURE_UNIT,
        ],
        "report_interval": {"default": 900, "min": 30, "unit": "s"},
    },
}

# Options for config_flow dropdown
MODEL_OPTIONS: Final = [
    {"value": model, "label": info["name"]} for model, info in DEVICE_MODELS.items()
]

# JSON protocol devices
JSON_MODELS: Final = [m for m in ("cgs1", "cgs2", "cgdn1") if m in DEVICE_MODELS]

# TLV protocol devices
TLV_MODELS: Final = [m for m in DEVICE_MODELS if m not in JSON_MODELS]
