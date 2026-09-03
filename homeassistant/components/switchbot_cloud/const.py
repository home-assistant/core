"""Constants for the SwitchBot Cloud integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "switchbot_cloud"
ENTRY_TITLE = "SwitchBot Cloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=600)

CONF_CLOUDHOOK_URL: Final = "cloudhook_url"

SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_HUMIDITY = "humidity"
SENSOR_KIND_BATTERY = "battery"

VACUUM_FAN_SPEED_QUIET = "quiet"
VACUUM_FAN_SPEED_STANDARD = "standard"
VACUUM_FAN_SPEED_STRONG = "strong"
VACUUM_FAN_SPEED_MAX = "max"


CLIMATE_PRESET_SCHEDULE = "schedule"

AI_ART_FRAME_UPLOAD_IMAGE_SERVICE = "upload_art_frame_image"

AFTER_COMMAND_REFRESH = 5
COVER_ENTITY_AFTER_COMMAND_REFRESH = 10
SMART_RADIATOR_THERMOSTAT_AFTER_COMMAND_REFRESH = 30

HUMIDITY_LEVELS = {
    34: 101,  # Low humidity mode
    67: 102,  # Medium humidity mode
    100: 103,  # High humidity mode
}

NIGHT_LIGHT_ON = "on"
NIGHT_LIGHT_OFF = "off"
NIGHT_LIGHT_BRIGHT = "bright"
NIGHT_LIGHT_SOFT = "soft"

STANDING_FAN_NIGHT_LIGHT_PARAMETERS_MAP = {
    NIGHT_LIGHT_ON: "on",
    NIGHT_LIGHT_OFF: "off",
    NIGHT_LIGHT_BRIGHT: "1",
    NIGHT_LIGHT_SOFT: "2",
}

BATTERY_CIRCULATOR_FAN_2_PRO_NIGHT_LIGHT_PARAMETERS_MAP = {
    NIGHT_LIGHT_ON: "on",
    NIGHT_LIGHT_OFF: "off",
    NIGHT_LIGHT_BRIGHT: "0",
    NIGHT_LIGHT_SOFT: "1",
}


@dataclass(frozen=True)
class SwitchbotCloudDeviceConfig:
    """Switchbot Cloud Device Config."""

    webhook: bool
    entity_config: tuple[Platform, ...]


DEVICE_SUPPORT_MAP: Final[dict[str, SwitchbotCloudDeviceConfig]] = {
    "Motion Sensor": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.SENSOR)
    ),
    "Contact Sensor": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.SENSOR)
    ),
    "Presence Sensor": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.SENSOR)
    ),
    "Hub 3": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.SENSOR)
    ),
    "Home Climate Panel": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.SENSOR)
    ),
    "WeatherStation": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR,)
    ),
    "Meter": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.SENSOR,)),
    "MeterPlus": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.SENSOR,)),
    "WoIOSensor": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.SENSOR,)),
    "Hub 2": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.SENSOR,)),
    "MeterPro": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.SENSOR,)),
    "Smart Lock": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.SENSOR, Platform.LOCK)
    ),
    "Smart Lock Ultra": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Smart Lock Ultra Max": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Smart Lock Vision": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Smart Lock Vision Pro": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Lock Vision": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Lock Vision Pro": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Smart Lock Lite": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Smart Lock Pro": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Smart Lock Pro Wifi": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LOCK)
    ),
    "Strip Light": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.LIGHT,)),
    "Strip Light 3": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.LIGHT,)),
    "Floor Lamp": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.LIGHT,)),
    "Color Bulb": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.LIGHT,)),
    "RGBICWW Floor Lamp": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "Permanent Outdoor Lights": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "RGBICWW Strip Light": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "Ceiling Light": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.LIGHT,)),
    "Ceiling Light Pro": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "RGBIC Neon Wire Rope Light": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "RGBIC Neon Rope Light": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "Candle Warmer Lamp": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.LIGHT,)
    ),
    "MeterPro(CO2)": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.SENSOR,)),
    "AI Art Frame": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BUTTON, Platform.IMAGE)
    ),
    "Circulator Fan": SwitchbotCloudDeviceConfig(True, entity_config=(Platform.FAN,)),
    "Standing Fan": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.FAN, Platform.SELECT)
    ),
    "Battery Circulator Fan": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.FAN, Platform.SELECT)
    ),
    "Battery Circulator Fan 2 Pro": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.FAN, Platform.SELECT)
    ),
    "Water Detector": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR)
    ),
    "Curtain": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.COVER)
    ),
    "Curtain3": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.COVER)
    ),
    "Curtain4": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.COVER)
    ),
    "Roller Shade": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.COVER)
    ),
    "Blind Tilt": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.SENSOR, Platform.BINARY_SENSOR, Platform.COVER)
    ),
    "Garage Door Opener": SwitchbotCloudDeviceConfig(
        True, entity_config=(Platform.BINARY_SENSOR, Platform.COVER)
    ),
}
