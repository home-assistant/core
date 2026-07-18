"""Sensor platform for the WattWächter Plus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import WattwaechterConfigEntry, WattwaechterCoordinator
from .entity import WattwaechterEntity

PARALLEL_UPDATES = 0

KNOWN_OBIS_CODES: dict[str, SensorEntityDescription] = {
    # Energy meters (kWh) - total_increasing
    "1.8.0": SensorEntityDescription(
        key="1.8.0",
        translation_key="import_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "2.8.0": SensorEntityDescription(
        key="2.8.0",
        translation_key="export_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "1.8.1": SensorEntityDescription(
        key="1.8.1",
        translation_key="import_tariff_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "1.8.2": SensorEntityDescription(
        key="1.8.2",
        translation_key="import_tariff_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "2.8.1": SensorEntityDescription(
        key="2.8.1",
        translation_key="export_tariff_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "2.8.2": SensorEntityDescription(
        key="2.8.2",
        translation_key="export_tariff_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    # Power (W) - measurement
    "16.7.0": SensorEntityDescription(
        key="16.7.0",
        translation_key="active_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "36.7.0": SensorEntityDescription(
        key="36.7.0",
        translation_key="active_power_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "56.7.0": SensorEntityDescription(
        key="56.7.0",
        translation_key="active_power_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "76.7.0": SensorEntityDescription(
        key="76.7.0",
        translation_key="active_power_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # Voltage (V) - measurement
    "32.7.0": SensorEntityDescription(
        key="32.7.0",
        translation_key="voltage_phase",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "52.7.0": SensorEntityDescription(
        key="52.7.0",
        translation_key="voltage_phase",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "72.7.0": SensorEntityDescription(
        key="72.7.0",
        translation_key="voltage_phase",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # Current (A) - measurement
    "31.7.0": SensorEntityDescription(
        key="31.7.0",
        translation_key="current_phase",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "51.7.0": SensorEntityDescription(
        key="51.7.0",
        translation_key="current_phase",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "71.7.0": SensorEntityDescription(
        key="71.7.0",
        translation_key="current_phase",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    # Frequency (Hz) - measurement
    "14.7.0": SensorEntityDescription(
        key="14.7.0",
        translation_key="frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    # Power factor - measurement
    "13.7.0": SensorEntityDescription(
        key="13.7.0",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "33.7.0": SensorEntityDescription(
        key="33.7.0",
        translation_key="power_factor_phase",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "53.7.0": SensorEntityDescription(
        key="53.7.0",
        translation_key="power_factor_phase",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "73.7.0": SensorEntityDescription(
        key="73.7.0",
        translation_key="power_factor_phase",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
}

OBIS_PHASE: dict[str, str] = {
    "36.7.0": "L1",
    "56.7.0": "L2",
    "76.7.0": "L3",
    "32.7.0": "L1",
    "52.7.0": "L2",
    "72.7.0": "L3",
    "31.7.0": "L1",
    "51.7.0": "L2",
    "71.7.0": "L3",
    "33.7.0": "L1",
    "53.7.0": "L2",
    "73.7.0": "L3",
}


@dataclass(frozen=True, kw_only=True)
class WattwaechterDiagnosticSensorDescription(SensorEntityDescription):
    """Describes a WattWächter diagnostic sensor sourced from system info."""

    section: str
    field: str
    value_fn: Callable[[str], StateType] = lambda value: value
    entity_registry_enabled_default: bool = False


DIAGNOSTIC_SENSORS: tuple[WattwaechterDiagnosticSensorDescription, ...] = (
    WattwaechterDiagnosticSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        section="wifi",
        field="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=int,
    ),
    WattwaechterDiagnosticSensorDescription(
        key="ssid",
        translation_key="ssid",
        section="wifi",
        field="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WattwaechterDiagnosticSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        section="wifi",
        field="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WattwaechterDiagnosticSensorDescription(
        key="mdns_name",
        translation_key="mdns_name",
        section="wifi",
        field="mdns_name",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattwaechterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WattWächter sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        WattwaechterObisSensor(
            coordinator=coordinator,
            description=KNOWN_OBIS_CODES[obis_code],
            obis_code=obis_code,
        )
        for obis_code in coordinator.data.meter.values
        if obis_code in KNOWN_OBIS_CODES
    ]
    entities.extend(
        WattwaechterDiagnosticSensor(coordinator, description)
        for description in DIAGNOSTIC_SENSORS
    )
    async_add_entities(entities)


class WattwaechterObisSensor(WattwaechterEntity, SensorEntity):
    """Sensor for OBIS meter values."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        description: SensorEntityDescription,
        obis_code: str,
    ) -> None:
        """Initialize the OBIS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._obis_code = obis_code
        self._attr_unique_id = f"{coordinator.device_id}_{obis_code}"
        if obis_code in OBIS_PHASE:
            self._attr_translation_placeholders = {"phase": OBIS_PHASE[obis_code]}

    @property
    @override
    def native_value(self) -> float | str | None:
        """Return the current sensor value."""
        obis = self.coordinator.data.meter.values.get(self._obis_code)
        if obis is None:
            return None
        return obis.value


class WattwaechterDiagnosticSensor(WattwaechterEntity, SensorEntity):
    """Diagnostic sensor sourced from the device system info."""

    entity_description: WattwaechterDiagnosticSensorDescription

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        description: WattwaechterDiagnosticSensorDescription,
    ) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current diagnostic value."""
        system = self.coordinator.data.system
        if system is None:
            return None
        raw = system.get_value(
            self.entity_description.section, self.entity_description.field
        )
        if not raw:
            return None
        return self.entity_description.value_fn(raw)
