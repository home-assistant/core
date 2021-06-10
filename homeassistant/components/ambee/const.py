"""Constants for the Ambee integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO,
)

from .models import AmbeeSensor

DOMAIN: Final = "ambee"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

ATTR_ENABLED_BY_DEFAULT: Final = "enabled_by_default"
ATTR_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_SERVICE: Final = "service"

DEVICE_CLASS_AMBEE_RISK: Final = "ambee__risk"

SERVICE_AIR_QUALITY: Final = "air_quality"
SERVICE_POLLEN: Final = "pollen"

SERVICES: dict[str, str] = {
    SERVICE_AIR_QUALITY: "Air Quality",
    SERVICE_POLLEN: "Pollen",
}

SENSORS: dict[str, dict[str, AmbeeSensor]] = {
    SERVICE_AIR_QUALITY: {
        "particulate_matter_2_5": {
            ATTR_NAME: "Particulate Matter < 2.5 μm",
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "particulate_matter_10": {
            ATTR_NAME: "Particulate Matter < 10 μm",
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "sulphur_dioxide": {
            ATTR_NAME: "Sulphur Dioxide (SO2)",
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "nitrogen_dioxide": {
            ATTR_NAME: "Nitrogen Dioxide (NO2)",
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "ozone": {
            ATTR_NAME: "Ozone",
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "carbon_monoxide": {
            ATTR_NAME: "Carbon Monoxide (CO)",
            ATTR_DEVICE_CLASS: DEVICE_CLASS_CO,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
        "air_quality_index": {
            ATTR_NAME: "Air Quality Index (AQI)",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
    },
    SERVICE_POLLEN: {
        "grass": {
            ATTR_NAME: "Grass Pollen",
            ATTR_ICON: "mdi:grass",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
        },
        "tree": {
            ATTR_NAME: "Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
        },
        "weed": {
            ATTR_NAME: "Weed Pollen",
            ATTR_ICON: "mdi:sprout",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
        },
        "grass_risk": {
            ATTR_NAME: "Grass Pollen Risk",
            ATTR_ICON: "mdi:grass",
            ATTR_DEVICE_CLASS: DEVICE_CLASS_AMBEE_RISK,
        },
        "tree_risk": {
            ATTR_NAME: "Tree Pollen Risk",
            ATTR_ICON: "mdi:tree",
            ATTR_DEVICE_CLASS: DEVICE_CLASS_AMBEE_RISK,
        },
        "weed_risk": {
            ATTR_NAME: "Weed Pollen Risk",
            ATTR_ICON: "mdi:sprout",
            ATTR_DEVICE_CLASS: DEVICE_CLASS_AMBEE_RISK,
        },
        "grass_poaceae": {
            ATTR_NAME: "Poaceae Grass Pollen",
            ATTR_ICON: "mdi:grass",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_alder": {
            ATTR_NAME: "Alder Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_birch": {
            ATTR_NAME: "Birch Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_cypress": {
            ATTR_NAME: "Cypress Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_elm": {
            ATTR_NAME: "Elm Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_hazel": {
            ATTR_NAME: "Hazel Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_oak": {
            ATTR_NAME: "Oak Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_pine": {
            ATTR_NAME: "Pine Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_plane": {
            ATTR_NAME: "Plane Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "tree_poplar": {
            ATTR_NAME: "Poplar Tree Pollen",
            ATTR_ICON: "mdi:tree",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "weed_chenopod": {
            ATTR_NAME: "Chenopod Weed Pollen",
            ATTR_ICON: "mdi:sprout",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "weed_mugwort": {
            ATTR_NAME: "Mugwort Weed Pollen",
            ATTR_ICON: "mdi:sprout",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "weed_nettle": {
            ATTR_NAME: "Nettle Weed Pollen",
            ATTR_ICON: "mdi:sprout",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
        "weed_ragweed": {
            ATTR_NAME: "Ragweed Weed Pollen",
            ATTR_ICON: "mdi:sprout",
            ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_CUBIC_METER,
            ATTR_ENABLED_BY_DEFAULT: False,
        },
    },
}
