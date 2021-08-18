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

SENSORS: dict[str, list[SensorEntityDescription]] = {
    SERVICE_AIR_QUALITY: [
        SensorEntityDescription(
            key="particulate_matter_2_5",
            name="Particulate Matter < 2.5 μm",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="particulate_matter_10",
            name="Particulate Matter < 10 μm",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="sulphur_dioxide",
            name="Sulphur Dioxide (SO2)",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="nitrogen_dioxide",
            name="Nitrogen Dioxide (NO2)",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="ozone",
            name="Ozone",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="carbon_monoxide",
            name="Carbon Monoxide (CO)",
            device_class=DEVICE_CLASS_CO,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key="air_quality_index",
            name="Air Quality Index (AQI)",
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ],
    SERVICE_POLLEN: [
        SensorEntityDescription(
            key="grass",
            name="Grass Pollen",
            icon="mdi:grass",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        SensorEntityDescription(
            key="tree",
            name="Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        SensorEntityDescription(
            key="weed",
            name="Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        SensorEntityDescription(
            key="grass_risk",
            name="Grass Pollen Risk",
            icon="mdi:grass",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        SensorEntityDescription(
            key="tree_risk",
            name="Tree Pollen Risk",
            icon="mdi:tree",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        SensorEntityDescription(
            key="weed_risk",
            name="Weed Pollen Risk",
            icon="mdi:sprout",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        SensorEntityDescription(
            key="grass_poaceae",
            name="Poaceae Grass Pollen",
            icon="mdi:grass",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_alder",
            name="Alder Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_birch",
            name="Birch Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_cypress",
            name="Cypress Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_elm",
            name="Elm Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_hazel",
            name="Hazel Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_oak",
            name="Oak Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_pine",
            name="Pine Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_plane",
            name="Plane Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_poplar",
            name="Poplar Tree Pollen",
            icon="mdi:tree",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_chenopod",
            name="Chenopod Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_mugwort",
            name="Mugwort Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_nettle",
            name="Nettle Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_ragweed",
            name="Ragweed Weed Pollen",
            icon="mdi:sprout",
            state_class=STATE_CLASS_MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
    ],
}
