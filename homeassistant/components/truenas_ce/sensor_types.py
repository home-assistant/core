"""Definitions for TrueNAS sensor entities."""

from dataclasses import dataclass
from typing import Any, NamedTuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfRatio,
    UnitOfTemperature,
)

from .const import LINK_STATE_DOWN
from .entity import TrueNASEntityDescription

DEVICE_ATTRIBUTES_NETWORK = (
    "description",
    "mtu",
    "link_state",
    "active_media_type",
    "active_media_subtype",
    "link_address",
)

DEVICE_ATTRIBUTES_CPU: tuple[str, ...] = ()

DEVICE_ATTRIBUTES_MEMORY = (
    "memory-free_value",
    "memory-total_value",
)


# Descriptions live in this sibling module (not sensor.py) to stay easy to diff separately from the entity classes.
@dataclass(frozen=True, kw_only=True)
class TrueNASSensorEntityDescription(  # pylint: disable=home-assistant-enforce-class-module
    SensorEntityDescription, TrueNASEntityDescription
):
    """Class describing entities."""

    data_attribute: str | None = None
    # Skip creating an entity when data[key] == value, e.g. hide traffic sensors for a down NIC.
    data_exclude: tuple[str, Any] | None = None
    func: str = "TrueNASSensor"


SENSOR_TYPES: tuple[TrueNASSensorEntityDescription, ...] = (
    TrueNASSensorEntityDescription(
        key="system_uptime",
        translation_key="system_uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="uptimeEpoch",
        func="TrueNASUptimeSensor",
    ),
    TrueNASSensorEntityDescription(
        key="system_cpu_temperature",
        translation_key="system_cpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="cpu_temperature",
    ),
    TrueNASSensorEntityDescription(
        key="system_load_shortterm",
        translation_key="system_load_shortterm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="load_shortterm",
    ),
    TrueNASSensorEntityDescription(
        key="system_load_midterm",
        translation_key="system_load_midterm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="load_midterm",
    ),
    TrueNASSensorEntityDescription(
        key="system_load_longterm",
        translation_key="system_load_longterm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="load_longterm",
    ),
    TrueNASSensorEntityDescription(
        key="system_cpu_usage",
        translation_key="system_cpu_usage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="cpu_usage",
        data_attributes_list=DEVICE_ATTRIBUTES_CPU,
    ),
    TrueNASSensorEntityDescription(
        key="system_memory_usage",
        translation_key="system_memory_usage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="memory-usage_percent",
        data_attributes_list=DEVICE_ATTRIBUTES_MEMORY,
    ),
    TrueNASSensorEntityDescription(
        key="system_cache_size-arc_value",
        translation_key="system_cache_size_arc_value",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="cache_size-arc_value",
    ),
    TrueNASSensorEntityDescription(
        key="system_memory_total",
        translation_key="system_memory_total",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="memory-total_value",
        data_attributes_list=DEVICE_ATTRIBUTES_MEMORY,
    ),
    TrueNASSensorEntityDescription(
        key="system_memory_free",
        translation_key="system_memory_free",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="memory-free_value",
        data_attributes_list=DEVICE_ATTRIBUTES_MEMORY,
    ),
    TrueNASSensorEntityDescription(
        key="traffic_rx",
        translation_key="traffic_rx",
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        ha_group="Network",
        data_path="interface",
        data_attribute="rx",
        data_name="name",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_NETWORK,
        data_exclude=("link_state", LINK_STATE_DOWN),
    ),
    TrueNASSensorEntityDescription(
        key="traffic_tx",
        translation_key="traffic_tx",
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        ha_group="Network",
        data_path="interface",
        data_attribute="tx",
        data_name="name",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_NETWORK,
        data_exclude=("link_state", LINK_STATE_DOWN),
    ),
)


class SensorService(NamedTuple):
    """Service definition."""

    name: str
    schema: Any
    action: str
    admin_only: bool = False


# Empty in bronze scope; reintroduced in a follow-up PR (see quality_scale.yaml's action-setup rule).
SENSOR_SERVICES: tuple[SensorService, ...] = ()
