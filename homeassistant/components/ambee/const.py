"""Constants for the Ambee integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_NAME,
    ATTR_SERVICE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO,
)

DOMAIN: Final = "ambee"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=180)

SERVICE_AIR_QUALITY: Final = ("air_quality", "Air Quality")

SENSORS: dict[str, dict[str, Any]] = {
    "particulate_matter_2_5": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Particulate Matter < 2.5 μm",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "particulate_matter_10": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Particulate Matter < 10 μm",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "sulphur_dioxide": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Sulphur Dioxide (SO2)",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "nitrogen_dioxide": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Nitrogen Dioxide (NO2)",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "ozone": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Ozone",
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "carbon_monoxide": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Carbon Monoxide (CO)",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CO,
        ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    "air_quality_index": {
        ATTR_SERVICE: SERVICE_AIR_QUALITY,
        ATTR_NAME: "Air Quality Index (AQI)",
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
}
