"""Support for monitoring an OpenEVSE Charger."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import override

from openevsehttp.__main__ import OpenEVSE

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfInformation,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .coordinator import OpenEVSEConfigEntry
from .entity import OpenEVSEEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


STATUS_OPTIONS: list[str] = [
    "charging",
    "connected",
    "diode_check_failed",
    "disabled",
    "gfci_fault",
    "gfci_self_test_failure",
    "no_ground",
    "not_connected",
    "over_temperature",
    "sleeping",
    "stuck_relay",
    "vent_required",
]


def _map_status(status: str | None) -> str | None:
    """Map raw status string to enum option."""
    if status is not None and (slug := slugify(status)) in STATUS_OPTIONS:
        return slug
    return None


@dataclass(frozen=True, kw_only=True)
class OpenEVSESensorDescription(SensorEntityDescription):
    """Describes an OpenEVSE sensor entity."""

    value_fn: Callable[[OpenEVSE], str | float | datetime | None]


SENSOR_TYPES: tuple[OpenEVSESensorDescription, ...] = (
    # Status sensors
    OpenEVSESensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        value_fn=lambda ev: _map_status(ev.status),
    ),
    OpenEVSESensorDescription(
        key="service_level",
        translation_key="service_level",
        device_class=SensorDeviceClass.ENUM,
        options=["level_1", "level_2", "automatic"],
        value_fn=lambda ev: {
            "1": "level_1",
            "2": "level_2",
            "a": "automatic",
        }.get(str(ev.service_level).lower()),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Timing sensors
    OpenEVSESensorDescription(
        key="charge_time",
        translation_key="charge_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.charge_time_elapsed,
    ),
    OpenEVSESensorDescription(
        key="vehicle_eta",
        translation_key="vehicle_eta",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda ev: ev.vehicle_eta,
    ),
    # Electrical sensors
    OpenEVSESensorDescription(
        key="charging_current",
        translation_key="charging_current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.charging_current,
    ),
    OpenEVSESensorDescription(
        key="charging_voltage",
        translation_key="charging_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.charging_voltage,
    ),
    OpenEVSESensorDescription(
        key="charging_power",
        translation_key="charging_power",
        native_unit_of_measurement=UnitOfPower.MILLIWATT,
        suggested_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.charging_power,
    ),
    OpenEVSESensorDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.current_power,
    ),
    OpenEVSESensorDescription(
        key="current_capacity",
        translation_key="current_capacity",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.current_capacity,
    ),
    OpenEVSESensorDescription(
        key="max_current",
        translation_key="max_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda ev: ev.max_current,
    ),
    OpenEVSESensorDescription(
        key="min_amps",
        translation_key="min_amps",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.min_amps,
    ),
    OpenEVSESensorDescription(
        key="max_amps",
        translation_key="max_amps",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.max_amps,
    ),
    # Temperature sensors
    OpenEVSESensorDescription(
        key="ambient_temp",
        translation_key="ambient_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.ambient_temperature,
    ),
    OpenEVSESensorDescription(
        key="ir_temp",
        translation_key="ir_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.ir_temperature,
        entity_registry_enabled_default=False,
    ),
    OpenEVSESensorDescription(
        key="rtc_temp",
        translation_key="rtc_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.rtc_temperature,
        entity_registry_enabled_default=False,
    ),
    OpenEVSESensorDescription(
        key="esp_temp",
        translation_key="esp_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.esp_temperature,
    ),
    # Energy sensors
    OpenEVSESensorDescription(
        key="usage_session",
        translation_key="usage_session",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda ev: ev.usage_session,
    ),
    OpenEVSESensorDescription(
        key="usage_total",
        translation_key="usage_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda ev: ev.usage_total,
    ),
    OpenEVSESensorDescription(
        key="total_day",
        translation_key="total_day",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.total_day,
    ),
    OpenEVSESensorDescription(
        key="total_week",
        translation_key="total_week",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.total_week,
    ),
    OpenEVSESensorDescription(
        key="total_month",
        translation_key="total_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.total_month,
    ),
    OpenEVSESensorDescription(
        key="total_year",
        translation_key="total_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.total_year,
    ),
    # Vehicle sensors
    OpenEVSESensorDescription(
        key="vehicle_soc",
        translation_key="vehicle_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.vehicle_soc,
    ),
    OpenEVSESensorDescription(
        key="vehicle_range",
        translation_key="vehicle_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.vehicle_range,
    ),
    # Connectivity sensors
    OpenEVSESensorDescription(
        key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.wifi_signal,
    ),
    # Power shaper sensors
    OpenEVSESensorDescription(
        key="shaper_live_power",
        translation_key="shaper_live_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.shaper_live_power,
    ),
    OpenEVSESensorDescription(
        key="shaper_available_current",
        translation_key="shaper_available_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.shaper_available_current,
    ),
    OpenEVSESensorDescription(
        key="shaper_max_power",
        translation_key="shaper_max_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.shaper_max_power,
    ),
    # Safety trip count sensors
    OpenEVSESensorDescription(
        key="gfi_trip_count",
        translation_key="gfi_trip_count",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.gfi_trip_count,
    ),
    OpenEVSESensorDescription(
        key="no_gnd_trip_count",
        translation_key="no_gnd_trip_count",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.no_gnd_trip_count,
    ),
    OpenEVSESensorDescription(
        key="stuck_relay_trip_count",
        translation_key="stuck_relay_trip_count",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.stuck_relay_trip_count,
    ),
    # System diagnostic sensors
    OpenEVSESensorDescription(
        key="uptime",
        translation_key="uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.uptime,
    ),
    OpenEVSESensorDescription(
        key="freeram",
        translation_key="freeram",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.freeram,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE sensors based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSESensor(coordinator, description, identifier, entry.unique_id)
        for description in SENSOR_TYPES
    )


class OpenEVSESensor(OpenEVSEEntity, SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    entity_description: OpenEVSESensorDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.charger)
