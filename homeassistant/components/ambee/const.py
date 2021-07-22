"""Constants for the Ambee integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
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
        "particulate_matter_2_5": AmbeeSensor(
            name="Particulate Matter < 2.5 μm",
            unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "particulate_matter_10": AmbeeSensor(
            name="Particulate Matter < 10 μm",
            unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "sulphur_dioxide": AmbeeSensor(
            name="Sulphur Dioxide (SO2)",
            unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "nitrogen_dioxide": AmbeeSensor(
            name="Nitrogen Dioxide (NO2)",
            unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "ozone": AmbeeSensor(
            name="Ozone",
            unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "carbon_monoxide": AmbeeSensor(
            name="Carbon Monoxide (CO)",
            device_class=DEVICE_CLASS_CO,
            unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "air_quality_index": AmbeeSensor(
            name="Air Quality Index (AQI)",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    },
    SERVICE_POLLEN: {
        "grass": AmbeeSensor(
            name="Grass Pollen",
            icon="mdi:grass",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        "tree": AmbeeSensor(
            name="Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        "weed": AmbeeSensor(
            name="Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        "grass_risk": AmbeeSensor(
            name="Grass Pollen Risk",
            icon="mdi:grass",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        "tree_risk": AmbeeSensor(
            name="Tree Pollen Risk",
            icon="mdi:tree",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        "weed_risk": AmbeeSensor(
            name="Weed Pollen Risk",
            icon="mdi:sprout",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        "grass_poaceae": AmbeeSensor(
            name="Poaceae Grass Pollen",
            icon="mdi:grass",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_alder": AmbeeSensor(
            name="Alder Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_birch": AmbeeSensor(
            name="Birch Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_cypress": AmbeeSensor(
            name="Cypress Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_elm": AmbeeSensor(
            name="Elm Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_hazel": AmbeeSensor(
            name="Hazel Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_oak": AmbeeSensor(
            name="Oak Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_pine": AmbeeSensor(
            name="Pine Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_plane": AmbeeSensor(
            name="Plane Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "tree_poplar": AmbeeSensor(
            name="Poplar Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "weed_chenopod": AmbeeSensor(
            name="Chenopod Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "weed_mugwort": AmbeeSensor(
            name="Mugwort Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "weed_nettle": AmbeeSensor(
            name="Nettle Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
        "weed_ragweed": AmbeeSensor(
            name="Ragweed Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            enabled_by_default=False,
        ),
    },
}
