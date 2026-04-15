"""Constants for the SwitchBot Cloud integration."""

from datetime import timedelta
from enum import Enum
from typing import Final

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


class EntityTypeForMap(Enum):
    """Entity Type For Map."""

    BINARY_SENSOR = "binary_sensors"
    BUTTON = "buttons"
    CLIMATE = "climates"
    COVER = "covers"
    FAN = "fans"
    HUMIDIFIER = "humidifiers"
    IMAGE = "images"
    LIGHT = "lights"
    LOCK = "locks"
    SENSOR = "sensors"
    SWITCH = "switches"
    VACUUM = "vacuums"


DeviceSupportMap: dict[str, dict[str, bool | list[EntityTypeForMap]]] = {
    "Smart Radiator Thermostat": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.CLIMATE, EntityTypeForMap.SENSOR],
    },
    "Relay Switch 1PM": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.SWITCH, EntityTypeForMap.SENSOR],
    },
    "Relay Switch 1": {"webhook": False, "entity_list": [EntityTypeForMap.SWITCH]},
    "Relay Switch 2PM": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.SWITCH, EntityTypeForMap.SENSOR],
    },
    "K10+": {"webhook": True, "entity_list": [EntityTypeForMap.VACUUM]},
    "K10+ Pro": {"webhook": True, "entity_list": [EntityTypeForMap.VACUUM]},
    "Robot Vacuum Cleaner S1": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.VACUUM],
    },
    "Robot Vacuum Cleaner S1 Plus": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.VACUUM],
    },
    "K20+ Pro": {"webhook": True, "entity_list": [EntityTypeForMap.VACUUM]},
    "Robot Vacuum Cleaner K10+ Pro Combo": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.VACUUM],
    },
    "Robot Vacuum Cleaner S10": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.VACUUM],
    },
    "Robot Vacuum Cleaner S20": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.VACUUM],
    },
    "S20": {"webhook": True, "entity_list": [EntityTypeForMap.VACUUM]},
    "Robot Vacuum Cleaner K11 Plus": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.VACUUM],
    },
    "Smart Lock": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Smart Lock Lite": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Smart Lock Pro": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Smart Lock Ultra": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Smart Lock Vision": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Smart Lock Vision Pro": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Smart Lock Pro Wifi": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Lock Vision": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Lock Vision Pro": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.LOCK,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Motion Sensor": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.BINARY_SENSOR, EntityTypeForMap.SENSOR],
    },
    "Contact Sensor": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.BINARY_SENSOR, EntityTypeForMap.SENSOR],
    },
    "Presence Sensor": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.BINARY_SENSOR, EntityTypeForMap.SENSOR],
    },
    "Hub 3": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.BINARY_SENSOR, EntityTypeForMap.SENSOR],
    },
    "Water Detector": {
        "webhook": True,
        "entity_list": [EntityTypeForMap.BINARY_SENSOR, EntityTypeForMap.SENSOR],
    },
    "Battery Circulator Fan": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.FAN, EntityTypeForMap.SENSOR],
    },
    "Standing Fan": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.FAN, EntityTypeForMap.SENSOR],
    },
    "Circulator Fan": {"webhook": False, "entity_list": [EntityTypeForMap.FAN]},
    "Curtain": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.COVER,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Curtain3": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.COVER,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Roller Shade": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.COVER,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Blind Tilt": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.COVER,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.BINARY_SENSOR,
        ],
    },
    "Strip Light": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "Strip Light 3": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "Floor Lamp": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "Color Bulb": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "RGBICWW Floor Lamp": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "RGBICWW Strip Light": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "Ceiling Light": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "Ceiling Light Pro": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "RGBIC Neon Rope Light": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.LIGHT],
    },
    "RGBIC Neon Wire Rope Light": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.LIGHT],
    },
    "Candle Warmer Lamp": {"webhook": False, "entity_list": [EntityTypeForMap.LIGHT]},
    "Humidifier2": {"webhook": False, "entity_list": [EntityTypeForMap.HUMIDIFIER]},
    "Humidifier": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.HUMIDIFIER, EntityTypeForMap.SENSOR],
    },
    "Home Climate Panel": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.BINARY_SENSOR, EntityTypeForMap.SENSOR],
    },
    "AI Art Frame": {
        "webhook": False,
        "entity_list": [
            EntityTypeForMap.BUTTON,
            EntityTypeForMap.SENSOR,
            EntityTypeForMap.IMAGE,
        ],
    },
    "WeatherStation": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "Meter": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "MeterPlus": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "WoIOSensor": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "Hub 2": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "MeterPro": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "MeterPro(CO2)": {"webhook": False, "entity_list": [EntityTypeForMap.SENSOR]},
    "Plug": {"webhook": False, "entity_list": [EntityTypeForMap.SWITCH]},
    "Plug Mini (US)": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.SENSOR, EntityTypeForMap.SWITCH],
    },
    "Plug Mini (JP)": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.SENSOR, EntityTypeForMap.SWITCH],
    },
    "Plug Mini (EU)": {
        "webhook": False,
        "entity_list": [EntityTypeForMap.SENSOR, EntityTypeForMap.SWITCH],
    },
}
