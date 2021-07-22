"""Constants for the Ambee integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO,
)

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

SENSORS: dict[str, dict[str, SensorEntityDescription]] = {
    SERVICE_AIR_QUALITY: {
        "particulate_matter_2_5": SensorEntityDescription(
            name="Particulate Matter < 2.5 μm",
            unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "particulate_matter_10": SensorEntityDescription(
            name="Particulate Matter < 10 μm",
            unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "sulphur_dioxide": SensorEntityDescription(
            name="Sulphur Dioxide (SO2)",
            unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "nitrogen_dioxide": SensorEntityDescription(
            name="Nitrogen Dioxide (NO2)",
            unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "ozone": SensorEntityDescription(
            name="Ozone",
            unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "carbon_monoxide": SensorEntityDescription(
            name="Carbon Monoxide (CO)",
            device_class=DEVICE_CLASS_CO,
            unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        "air_quality_index": SensorEntityDescription(
            name="Air Quality Index (AQI)",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    },
    SERVICE_POLLEN: {
        "grass": SensorEntityDescription(
            name="Grass Pollen",
            icon="mdi:grass",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        "tree": SensorEntityDescription(
            name="Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        "weed": SensorEntityDescription(
            name="Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        "grass_risk": SensorEntityDescription(
            name="Grass Pollen Risk",
            icon="mdi:grass",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        "tree_risk": SensorEntityDescription(
            name="Tree Pollen Risk",
            icon="mdi:tree",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        "weed_risk": SensorEntityDescription(
            name="Weed Pollen Risk",
            icon="mdi:sprout",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        "grass_poaceae": SensorEntityDescription(
            name="Poaceae Grass Pollen",
            icon="mdi:grass",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_alder": SensorEntityDescription(
            name="Alder Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_birch": SensorEntityDescription(
            name="Birch Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_cypress": SensorEntityDescription(
            name="Cypress Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_elm": SensorEntityDescription(
            name="Elm Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_hazel": SensorEntityDescription(
            name="Hazel Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_oak": SensorEntityDescription(
            name="Oak Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_pine": SensorEntityDescription(
            name="Pine Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_plane": SensorEntityDescription(
            name="Plane Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "tree_poplar": SensorEntityDescription(
            name="Poplar Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "weed_chenopod": SensorEntityDescription(
            name="Chenopod Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "weed_mugwort": SensorEntityDescription(
            name="Mugwort Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "weed_nettle": SensorEntityDescription(
            name="Nettle Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        "weed_ragweed": SensorEntityDescription(
            name="Ragweed Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
    },
}
