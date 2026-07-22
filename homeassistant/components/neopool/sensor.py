"""Sensor platform for the NeoPool integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from neopool_modbus.capabilities import (
    has_filtvalve,
    has_heating_relay,
    has_variable_speed_pump,
    is_chlorine_module_present,
    is_conductivity_module_present,
    is_hydrolysis_present,
    is_ionization_present,
    is_ph_module_present,
    is_redox_module_present,
    is_temperature_active,
)
from neopool_modbus.decoders import (
    FILTRATION_MODE_LABELS,
    FILTRATION_SPEED_STATE_LABELS,
    HIDRO_POLARITY_LABELS,
    ION_POLARITY_LABELS,
    PH_STATUS_ALARM_LABELS,
    calculate_next_interval_time,
    decode_hidro_polarity,
    decode_ion_polarity,
    decode_ph_alarm,
    decode_ph_pump_status,
    is_hydrolysis_in_percent,
    ph_pump_options,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeoPoolConfigEntry
from .coordinator import NeoPoolCoordinator
from .entity import NeoPoolEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NeoPoolSensorEntityDescription(SensorEntityDescription):
    """Describes a NeoPool sensor entity."""

    supported_fn: Callable[[dict[str, Any]], bool] | None = None
    value_fn: Callable[[dict[str, Any]], Any] | None = None
    options_fn: Callable[[dict[str, Any]], list[str]] | None = None
    unit_fn: Callable[[dict[str, Any]], str | None] | None = None
    precision_fn: Callable[[dict[str, Any]], int | None] | None = None


SENSOR_DESCRIPTIONS: dict[str, NeoPoolSensorEntityDescription] = {
    "MBF_ION_CURRENT": NeoPoolSensorEntityDescription(
        key="MBF_ION_CURRENT",
        translation_key="ion_current",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=is_ionization_present,
    ),
    "MBF_HIDRO_CURRENT": NeoPoolSensorEntityDescription(
        key="MBF_HIDRO_CURRENT",
        translation_key="hidro_current",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=is_hydrolysis_present,
        unit_fn=lambda data: (
            UnitOfRatio.PERCENTAGE if is_hydrolysis_in_percent(data) else "g/h"
        ),
        precision_fn=lambda data: 0 if is_hydrolysis_in_percent(data) else 1,
    ),
    "MBF_MEASURE_PH": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_PH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=is_ph_module_present,
    ),
    "MBF_MEASURE_RX": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_RX",
        translation_key="measure_rx",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=is_redox_module_present,
    ),
    "MBF_MEASURE_CL": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_CL",
        translation_key="measure_cl",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=is_chlorine_module_present,
    ),
    "MBF_MEASURE_CONDUCTIVITY": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_CONDUCTIVITY",
        translation_key="measure_conductivity",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=is_conductivity_module_present,
    ),
    "MBF_MEASURE_TEMPERATURE": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_TEMPERATURE",
        translation_key="measure_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=is_temperature_active,
    ),
    "MBF_HIDRO_VOLTAGE": NeoPoolSensorEntityDescription(
        key="MBF_HIDRO_VOLTAGE",
        translation_key="hidro_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
    "MBF_PAR_FILT_MODE": NeoPoolSensorEntityDescription(
        key="MBF_PAR_FILT_MODE",
        translation_key="filt_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(FILTRATION_MODE_LABELS.values()),
        value_fn=lambda data: data.get("filtration_mode"),
    ),
    "MBF_PH_STATUS_ALARM": NeoPoolSensorEntityDescription(
        key="MBF_PH_STATUS_ALARM",
        translation_key="ph_status_alarm",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(PH_STATUS_ALARM_LABELS.values()),
        value_fn=decode_ph_alarm,
        supported_fn=is_ph_module_present,
    ),
    "HIDRO_POLARITY": NeoPoolSensorEntityDescription(
        key="HIDRO_POLARITY",
        translation_key="hidro_polarity",
        device_class=SensorDeviceClass.ENUM,
        options=list(HIDRO_POLARITY_LABELS),
        value_fn=decode_hidro_polarity,
        supported_fn=is_hydrolysis_present,
    ),
    "ION_POLARITY": NeoPoolSensorEntityDescription(
        key="ION_POLARITY",
        translation_key="ion_polarity",
        device_class=SensorDeviceClass.ENUM,
        options=list(ION_POLARITY_LABELS),
        value_fn=decode_ion_polarity,
        supported_fn=is_ionization_present,
    ),
    "PH_PUMP_STATUS": NeoPoolSensorEntityDescription(
        key="PH_PUMP_STATUS",
        translation_key="ph_pump_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options_fn=ph_pump_options,
        value_fn=decode_ph_pump_status,
        supported_fn=is_ph_module_present,
    ),
    "FILTRATION_SPEED": NeoPoolSensorEntityDescription(
        key="FILTRATION_SPEED",
        translation_key="filtration_speed",
        device_class=SensorDeviceClass.ENUM,
        options=list(FILTRATION_SPEED_STATE_LABELS),
        value_fn=lambda data: data.get("filtration_speed_state"),
        supported_fn=has_variable_speed_pump,
    ),
    "MBF_PAR_INTELLIGENT_INTERVALS": NeoPoolSensorEntityDescription(
        key="MBF_PAR_INTELLIGENT_INTERVALS",
        translation_key="intelligent_intervals",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data: (
            has_heating_relay(data) and is_temperature_active(data)
        ),
    ),
    "MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL": NeoPoolSensorEntityDescription(
        key="MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL",
        translation_key="intelligent_tt_next_interval",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: calculate_next_interval_time(
            data.get("MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL")
        ),
        supported_fn=lambda data: (
            has_heating_relay(data) and is_temperature_active(data)
        ),
    ),
    "MBF_PAR_FILTVALVE_REMAINING": NeoPoolSensorEntityDescription(
        key="MBF_PAR_FILTVALVE_REMAINING",
        translation_key="filtvalve_remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=has_filtvalve,
    ),
    "CELL_RUNTIME_TOTAL": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_TOTAL",
        translation_key="cell_runtime_total",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
    "CELL_RUNTIME_PART": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_PART",
        translation_key="cell_runtime_part",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
    "CELL_RUNTIME_POLA": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_POLA",
        translation_key="cell_runtime_pola",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
    "CELL_RUNTIME_POLB": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_POLB",
        translation_key="cell_runtime_polb",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
    "CELL_RUNTIME_POL_CHANGES": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_POL_CHANGES",
        translation_key="cell_runtime_pol_changes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=is_hydrolysis_present,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        NeoPoolSensor(coordinator, key, desc)
        for key, desc in SENSOR_DESCRIPTIONS.items()
        if desc.supported_fn is None or desc.supported_fn(coordinator.data)
    )


_PRODUCTION_KEYS_REQUIRING_FILTRATION = frozenset(
    {
        "MBF_HIDRO_CURRENT",
        "MBF_HIDRO_VOLTAGE",
        "MBF_ION_CURRENT",
    }
)

_MEASURE_KEYS_REQUIRING_FILTRATION = frozenset(
    {
        "MBF_MEASURE_TEMPERATURE",
        "MBF_MEASURE_PH",
        "MBF_MEASURE_RX",
        "MBF_MEASURE_CL",
        "MBF_MEASURE_CONDUCTIVITY",
    }
)


class NeoPoolSensor(NeoPoolEntity, SensorEntity):
    """Representation of a NeoPool sensor."""

    entity_description: NeoPoolSensorEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        key: str,
        description: NeoPoolSensorEntityDescription,
    ) -> None:
        """Initialize the NeoPool sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._key = key
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.unique_id}_{key.lower()}"
        )

    @property
    @override
    def suggested_display_precision(self) -> int | None:
        """Return the suggested display precision for the sensor value."""
        if (precision_fn := self.entity_description.precision_fn) is not None:
            return precision_fn(self.coordinator.data)
        return super().suggested_display_precision

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the sensor value."""
        if (unit_fn := self.entity_description.unit_fn) is not None:
            return unit_fn(self.coordinator.data)
        return super().native_unit_of_measurement

    def _filtration_off(self) -> bool:
        """Return True when the filtration pump is off."""
        return self.coordinator.data.get("Filtration Pump") is False

    def _is_measurement_suppressed(self) -> bool:
        """Return True if a measurement sensor should report None."""
        if self._key not in _MEASURE_KEYS_REQUIRING_FILTRATION:
            return False
        return self._filtration_off()

    def _is_production_suppressed(self) -> bool:
        """Return True if a production sensor should report 0."""
        if self._key not in _PRODUCTION_KEYS_REQUIRING_FILTRATION:
            return False
        return self._filtration_off()

    @property
    @override
    def native_value(self) -> float | int | str | datetime | None:
        """Return the actual sensor value from coordinator data."""
        if self._is_measurement_suppressed():
            return None
        if self._is_production_suppressed():
            return 0
        if (value_fn := self.entity_description.value_fn) is not None:
            value: float | int | str | datetime | None = value_fn(self.coordinator.data)
            return value
        return self.coordinator.data.get(self._key)

    @property
    @override
    def options(self) -> list[str] | None:
        """Return the list of options for the sensor."""
        if (options_fn := self.entity_description.options_fn) is not None:
            return options_fn(self.coordinator.data)
        return super().options
