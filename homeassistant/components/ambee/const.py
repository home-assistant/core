"""Constants for the Ambee integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
)

DOMAIN: Final = "ambee"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

DEVICE_CLASS_AMBEE_RISK: Final = "ambee__risk"

SERVICE_AIR_QUALITY: Final = "air_quality"
SERVICE_POLLEN: Final = "pollen"

SERVICES: dict[str, str] = {
    SERVICE_AIR_QUALITY: "Air quality",
    SERVICE_POLLEN: "Pollen",
}

SENSORS: dict[str, list[SensorEntityDescription]] = {
    SERVICE_AIR_QUALITY: [
        SensorEntityDescription(
            key="particulate_matter_2_5",
            name="Particulate matter < 2.5 μm",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="particulate_matter_10",
            name="Particulate matter < 10 μm",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="sulphur_dioxide",
            name="Sulphur dioxide (SO2)",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="nitrogen_dioxide",
            name="Nitrogen dioxide (NO2)",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="ozone",
            name="Ozone",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="carbon_monoxide",
            name="Carbon monoxide (CO)",
            device_class=SensorDeviceClass.CO,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="air_quality_index",
            name="Air quality index (AQI)",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ],
    SERVICE_POLLEN: [
        SensorEntityDescription(
            key="grass",
            name="Grass",
            icon="mdi:grass",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        SensorEntityDescription(
            key="tree",
            name="Tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        SensorEntityDescription(
            key="weed",
            name="Weed",
            icon="mdi:sprout",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        ),
        SensorEntityDescription(
            key="grass_risk",
            name="Grass risk",
            icon="mdi:grass",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        SensorEntityDescription(
            key="tree_risk",
            name="Tree risk",
            icon="mdi:tree",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        SensorEntityDescription(
            key="weed_risk",
            name="Weed risk",
            icon="mdi:sprout",
            device_class=DEVICE_CLASS_AMBEE_RISK,
        ),
        SensorEntityDescription(
            key="grass_poaceae",
            name="Poaceae grass",
            icon="mdi:grass",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_alder",
            name="Alder tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_birch",
            name="Birch tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_cypress",
            name="Cypress tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_elm",
            name="Elm tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_hazel",
            name="Hazel tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_oak",
            name="Oak tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_pine",
            name="Pine tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_plane",
            name="Plane tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="tree_poplar",
            name="Poplar tree",
            icon="mdi:tree",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_chenopod",
            name="Chenopod weed",
            icon="mdi:sprout",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_mugwort",
            name="Mugwort weed",
            icon="mdi:sprout",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_nettle",
            name="Nettle weed",
            icon="mdi:sprout",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="weed_ragweed",
            name="Ragweed weed",
            icon="mdi:sprout",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
        ),
    ],
}
