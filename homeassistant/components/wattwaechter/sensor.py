"""Sensor platform for the WattWächter Plus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aio_wattwaechter.models import ObisValue

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
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
    "1.6.0": SensorEntityDescription(
        key="1.6.0",
        translation_key="maximum_demand",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "15.8.0": SensorEntityDescription(
        key="15.8.0",
        translation_key="absolute_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "3.8.0": SensorEntityDescription(
        key="3.8.0",
        translation_key="reactive_energy_import",
        native_unit_of_measurement=(
            UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR
        ),
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "4.8.0": SensorEntityDescription(
        key="4.8.0",
        translation_key="reactive_energy_export",
        native_unit_of_measurement=(
            UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR
        ),
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "1.7.0": SensorEntityDescription(
        key="1.7.0",
        translation_key="active_power_import",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "2.7.0": SensorEntityDescription(
        key="2.7.0",
        translation_key="active_power_export",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "15.7.0": SensorEntityDescription(
        key="15.7.0",
        translation_key="absolute_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "3.7.0": SensorEntityDescription(
        key="3.7.0",
        translation_key="reactive_power_import",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "4.7.0": SensorEntityDescription(
        key="4.7.0",
        translation_key="reactive_power_export",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "9.7.0": SensorEntityDescription(
        key="9.7.0",
        translation_key="apparent_power_import",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "10.7.0": SensorEntityDescription(
        key="10.7.0",
        translation_key="apparent_power_export",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "5.8.0": SensorEntityDescription(
        key="5.8.0",
        translation_key="reactive_energy_quadrant_1",
        native_unit_of_measurement=(
            UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR
        ),
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "6.8.0": SensorEntityDescription(
        key="6.8.0",
        translation_key="reactive_energy_quadrant_2",
        native_unit_of_measurement=(
            UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR
        ),
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "7.8.0": SensorEntityDescription(
        key="7.8.0",
        translation_key="reactive_energy_quadrant_3",
        native_unit_of_measurement=(
            UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR
        ),
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "8.8.0": SensorEntityDescription(
        key="8.8.0",
        translation_key="reactive_energy_quadrant_4",
        native_unit_of_measurement=(
            UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR
        ),
        device_class=SensorDeviceClass.REACTIVE_ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
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

# Fallback mapping for momentary readings of OBIS codes without a dedicated
# description, keyed by the reported unit.
UNIT_MAP: dict[str, tuple[SensorDeviceClass, SensorStateClass]] = {
    UnitOfPower.WATT: (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    UnitOfElectricPotential.VOLT: (
        SensorDeviceClass.VOLTAGE,
        SensorStateClass.MEASUREMENT,
    ),
    UnitOfElectricCurrent.AMPERE: (
        SensorDeviceClass.CURRENT,
        SensorStateClass.MEASUREMENT,
    ),
    UnitOfFrequency.HERTZ: (SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT),
}

# Units that mark an x.8.y register as a cumulative energy total.
CUMULATIVE_ENERGY_UNITS: dict[str, SensorDeviceClass] = {
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR: (
        SensorDeviceClass.REACTIVE_ENERGY
    ),
}

# Identifier registers (device address, firmware revision, serial number)
# carry nothing to observe or automate on, so no entities are created for
# them. Other codes in the 0.x/96.x service groups can hold observable
# values (e.g. 96.5.0 operating status) and stay in the generic fallback.
# The raw identifier values remain available in the diagnostics download.
METADATA_OBIS_CODES = {"0.0.0", "0.2.0", "96.1.0"}


def _is_cumulative_register(obis_code: str) -> bool:
    """Return True for x.8.y registers, the OBIS cumulative energy totals."""
    parts = obis_code.split(".")
    return len(parts) == 3 and parts[1] == "8"


@dataclass(frozen=True, kw_only=True)
class WattwaechterDiagnosticSensorDescription(SensorEntityDescription):
    """Describes a WattWächter diagnostic sensor sourced from system info."""

    section: str
    field: str
    value_fn: Callable[[str], StateType] = lambda value: value


DIAGNOSTIC_SENSORS: tuple[WattwaechterDiagnosticSensorDescription, ...] = (
    WattwaechterDiagnosticSensorDescription(
        key="wifi_signal",
        section="wifi",
        field="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=int,
    ),
    WattwaechterDiagnosticSensorDescription(
        key="ssid",
        translation_key="ssid",
        section="wifi",
        field="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattwaechterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WattWächter sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    for obis_code, obis_value in coordinator.data.meter.values.items():
        if obis_code in KNOWN_OBIS_CODES:
            entities.append(
                WattwaechterObisSensor(
                    coordinator=coordinator,
                    description=KNOWN_OBIS_CODES[obis_code],
                    obis_code=obis_code,
                )
            )
        elif obis_code not in METADATA_OBIS_CODES:
            entities.append(
                WattwaechterGenericObisSensor(coordinator, obis_code, obis_value)
            )
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


class WattwaechterGenericObisSensor(WattwaechterEntity, SensorEntity):
    """Sensor for an OBIS code without a dedicated description."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        obis_code: str,
        obis_value: ObisValue,
    ) -> None:
        """Initialize the generic OBIS sensor."""
        super().__init__(coordinator)
        self._obis_code = obis_code
        self._attr_unique_id = f"{coordinator.device_id}_{obis_code}"
        self._attr_name = obis_value.name or f"OBIS {obis_code}"
        if isinstance(obis_value.value, str):
            return
        self._attr_native_unit_of_measurement = obis_value.unit or None
        if (
            device_class := CUMULATIVE_ENERGY_UNITS.get(obis_value.unit)
        ) and _is_cumulative_register(obis_code):
            # total_increasing also absorbs resets from a meter exchange.
            self._attr_device_class = device_class
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif mapping := UNIT_MAP.get(obis_value.unit):
            self._attr_device_class, self._attr_state_class = mapping

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
