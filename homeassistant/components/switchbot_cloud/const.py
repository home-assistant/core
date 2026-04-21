"""Constants for the SwitchBot Cloud integration."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "switchbot_cloud"
ENTRY_TITLE = "SwitchBot Cloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=600)

SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_HUMIDITY = "humidity"
SENSOR_KIND_BATTERY = "battery"

VACUUM_FAN_SPEED_QUIET = "quiet"
VACUUM_FAN_SPEED_STANDARD = "standard"
VACUUM_FAN_SPEED_STRONG = "strong"
VACUUM_FAN_SPEED_MAX = "max"


CLIMATE_PRESET_SCHEDULE = "schedule"

AFTER_COMMAND_REFRESH = 5
COVER_ENTITY_AFTER_COMMAND_REFRESH = 10
SMART_RADIATOR_THERMOSTAT_AFTER_COMMAND_REFRESH = 30

HUMIDITY_LEVELS = {
    34: 101,  # Low humidity mode
    67: 102,  # Medium humidity mode
    100: 103,  # High humidity mode
}


class AirPurifierMode(Enum):
    """Air Purifier Modes."""

    NORMAL = 1
    AUTO = 2
    SLEEP = 3
    PET = 4

    @classmethod
    def get_modes(cls) -> list[str]:
        """Return a list of available air purifier modes as lowercase strings."""
        return [mode.name.lower() for mode in cls]


class Humidifier2Mode(Enum):
    """Enumerates the available modes for a SwitchBot humidifier2."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3
    QUIET = 4
    TARGET_HUMIDITY = 5
    SLEEP = 6
    AUTO = 7
    DRYING_FILTER = 8

    @classmethod
    def get_modes(cls) -> list[str]:
        """Return a list of available humidifier2 modes as lowercase strings."""
        return [mode.name.lower() for mode in cls]


@dataclass(frozen=True)
class SwitchbotCloudDeviceConfig:
    """Switchbot Cloud Device Config."""

    webhook: bool
    entity_config: list[Platform]


DEVICE_SUPPORT_MAP: Final[dict[str, SwitchbotCloudDeviceConfig]] = {
    "Smart Radiator Thermostat": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.CLIMATE, Platform.SENSOR]
    ),
    "Relay Switch 1PM": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SWITCH, Platform.SENSOR]
    ),
    "Relay Switch 1": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SWITCH]
    ),
    "Relay Switch 2PM": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SWITCH, Platform.SENSOR]
    ),
    "K10+": SwitchbotCloudDeviceConfig(True, entity_config=[Platform.VACUUM]),
    "K10+ Pro": SwitchbotCloudDeviceConfig(True, entity_config=[Platform.VACUUM]),
    "Robot Vacuum Cleaner S1": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.VACUUM]
    ),
    "Robot Vacuum Cleaner S1 Plus": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.VACUUM]
    ),
    "K20+ Pro": SwitchbotCloudDeviceConfig(True, entity_config=[Platform.VACUUM]),
    "Robot Vacuum Cleaner K10+ Pro Combo": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.VACUUM]
    ),
    "Robot Vacuum Cleaner S10": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.VACUUM]
    ),
    "Robot Vacuum Cleaner S20": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.VACUUM]
    ),
    "S20": SwitchbotCloudDeviceConfig(True, entity_config=[Platform.VACUUM]),
    "Robot Vacuum Cleaner K11 Plus": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.VACUUM]
    ),
    "Smart Lock": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Smart Lock Lite": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Smart Lock Pro": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Smart Lock Ultra": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Smart Lock Vision": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Smart Lock Vision Pro": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Smart Lock Pro Wifi": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Lock Vision": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Lock Vision Pro": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LOCK, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Motion Sensor": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.BINARY_SENSOR, Platform.SENSOR]
    ),
    "Contact Sensor": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.BINARY_SENSOR, Platform.SENSOR]
    ),
    "Presence Sensor": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.BINARY_SENSOR, Platform.SENSOR]
    ),
    "Hub 3": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.BINARY_SENSOR, Platform.SENSOR]
    ),
    "Water Detector": SwitchbotCloudDeviceConfig(
        True, entity_config=[Platform.BINARY_SENSOR, Platform.SENSOR]
    ),
    "Battery Circulator Fan": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.FAN, Platform.SENSOR]
    ),
    "Standing Fan": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.FAN, Platform.SENSOR]
    ),
    "Circulator Fan": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.FAN]),
    "Curtain": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Curtain3": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Roller Shade": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Blind Tilt": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.COVER, Platform.SENSOR, Platform.BINARY_SENSOR]
    ),
    "Strip Light": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.LIGHT]),
    "Strip Light 3": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.LIGHT]),
    "Floor Lamp": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.LIGHT]),
    "Color Bulb": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.LIGHT]),
    "RGBICWW Floor Lamp": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LIGHT]
    ),
    "RGBICWW Strip Light": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LIGHT]
    ),
    "Ceiling Light": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.LIGHT]),
    "Ceiling Light Pro": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LIGHT]
    ),
    "RGBIC Neon Rope Light": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LIGHT]
    ),
    "RGBIC Neon Wire Rope Light": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LIGHT]
    ),
    "Candle Warmer Lamp": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.LIGHT]
    ),
    "Humidifier2": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.HUMIDIFIER]
    ),
    "Humidifier": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.HUMIDIFIER, Platform.SENSOR]
    ),
    "Home Climate Panel": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.BINARY_SENSOR, Platform.SENSOR]
    ),
    "AI Art Frame": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.BUTTON, Platform.SENSOR, Platform.IMAGE]
    ),
    "WeatherStation": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SENSOR]
    ),
    "Meter": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SENSOR]),
    "MeterPlus": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SENSOR]),
    "WoIOSensor": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SENSOR]),
    "Hub 2": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SENSOR]),
    "MeterPro": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SENSOR]),
    "MeterPro(CO2)": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SENSOR]),
    "Plug": SwitchbotCloudDeviceConfig(False, entity_config=[Platform.SWITCH]),
    "Plug Mini (US)": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SENSOR, Platform.SWITCH]
    ),
    "Plug Mini (JP)": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SENSOR, Platform.SWITCH]
    ),
    "Plug Mini (EU)": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.SENSOR, Platform.SWITCH]
    ),
    "Garage Door Opener": SwitchbotCloudDeviceConfig(
        False, entity_config=[Platform.COVER, Platform.BINARY_SENSOR]
    ),
}
