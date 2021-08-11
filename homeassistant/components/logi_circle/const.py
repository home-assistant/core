"""Constants in Logi Circle component."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import PERCENTAGE

DOMAIN = "logi_circle"
DATA_LOGI = DOMAIN

CONF_REDIRECT_URI = "redirect_uri"

DEFAULT_CACHEDB = ".logi_cache.pickle"


LED_MODE_KEY = "LED"
RECORDING_MODE_KEY = "RECORDING_MODE"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_level",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-50",
    ),
    SensorEntityDescription(
        key="last_activity_time",
        name="Last Activity",
        icon="mdi:history",
    ),
    SensorEntityDescription(
        key="recording",
        name="Recording Mode",
        icon="mdi:eye",
    ),
    SensorEntityDescription(
        key="signal_strength_category",
        name="WiFi Signal Category",
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key="signal_strength_percentage",
        name="WiFi Signal Strength",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key="streaming",
        name="Streaming Mode",
        icon="mdi:camera",
    ),
)

SIGNAL_LOGI_CIRCLE_RECONFIGURE = "logi_circle_reconfigure"
SIGNAL_LOGI_CIRCLE_SNAPSHOT = "logi_circle_snapshot"
SIGNAL_LOGI_CIRCLE_RECORD = "logi_circle_record"

# Attribution
ATTRIBUTION = "Data provided by circle.logi.com"
DEVICE_BRAND = "Logitech"
