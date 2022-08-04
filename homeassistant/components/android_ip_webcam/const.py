"""Constants for the Android IP Webcam integration."""

from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.helpers.entity import EntityCategory

DOMAIN: Final = "android_ip_webcam"
DEFAULT_NAME: Final = "IP Webcam"
DEFAULT_PORT: Final = 8080
DEFAULT_TIMEOUT: Final = 10

CONF_MOTION_SENSOR: Final = "motion_sensor"

MOTION_ACTIVE: Final = "motion_active"
SCAN_INTERVAL: Final = timedelta(seconds=10)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="audio_connections",
        name="Audio Connections",
        icon="mdi:speaker",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        icon="mdi:battery",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_temp",
        name="Battery Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="battery_voltage",
        name="Battery Voltage",
        icon="mdi:battery-charging-100",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="light",
        name="Light Level",
        icon="mdi:flashlight",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="motion",
        name="Motion",
        icon="mdi:run",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        icon="mdi:gauge",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="proximity",
        name="Proximity",
        icon="mdi:map-marker-radius",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="sound",
        name="Sound",
        icon="mdi:speaker",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="video_connections",
        name="Video Connections",
        icon="mdi:eye",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="exposure_lock",
        name="Exposure Lock",
        icon="mdi:camera",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="ffc",
        name="Front-facing Camera",
        icon="mdi:camera-front-variant",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="focus",
        name="Focus",
        icon="mdi:image-filter-center-focus",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="gps_active",
        name="GPS Active",
        icon="mdi:crosshairs-gps",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="motion_detect",
        name="Motion Detection",
        icon="mdi:flash",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="night_vision",
        name="Night Vision",
        icon="mdi:weather-night",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="overlay",
        name="Overlay",
        icon="mdi:monitor",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="torch",
        name="Torch",
        icon="mdi:white-balance-sunny",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="whitebalance_lock",
        name="White Balance Lock",
        icon="mdi:white-balance-auto",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="video_recording",
        name="Video Recording",
        icon="mdi:record-rec",
        entity_category=EntityCategory.CONFIG,
    ),
)

SWITCHES = [
    "exposure_lock",
    "ffc",
    "focus",
    "gps_active",
    "motion_detect",
    "night_vision",
    "overlay",
    "torch",
    "whitebalance_lock",
    "video_recording",
]

SENSORS = [
    "audio_connections",
    "battery_level",
    "battery_temp",
    "battery_voltage",
    "light",
    "motion",
    "pressure",
    "proximity",
    "sound",
    "video_connections",
]
