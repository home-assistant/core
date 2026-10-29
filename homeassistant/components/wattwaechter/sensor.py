"""Sensor platform for the WattWächter integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aio_wattwaechter.models import (
    OBIS_GAS_FLOW,
    OBIS_GAS_VOLUME,
    OBIS_WATER_FLOW,
    OBIS_WATER_VOLUME,
    Medium,
    ObisValue,
)

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
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
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import OBIS_GAS_POWER
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
    "21.7.0": SensorEntityDescription(
        key="21.7.0",
        translation_key="active_power_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    "41.7.0": SensorEntityDescription(
        key="41.7.0",
        translation_key="active_power_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    "61.7.0": SensorEntityDescription(
        key="61.7.0",
        translation_key="active_power_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    "22.7.0": SensorEntityDescription(
        key="22.7.0",
        translation_key="active_power_export_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    "42.7.0": SensorEntityDescription(
        key="42.7.0",
        translation_key="active_power_export_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    "62.7.0": SensorEntityDescription(
        key="62.7.0",
        translation_key="active_power_export_phase",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
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
    # Gas and water meters (WattWächter Gas / Wasser) report full OBIS codes
    # with the medium in value group A (7 gas, 8 cold water). The volume is a
    # total with last_reset: a correction of the reading on the device counts
    # as consumption (also downwards), a meter exchange starts a new cycle.
    OBIS_GAS_VOLUME: SensorEntityDescription(
        key=OBIS_GAS_VOLUME,
        translation_key="gas_consumption",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
    ),
    OBIS_GAS_FLOW: SensorEntityDescription(
        key=OBIS_GAS_FLOW,
        translation_key="gas_flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    OBIS_GAS_POWER: SensorEntityDescription(
        key=OBIS_GAS_POWER,
        translation_key="gas_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    OBIS_WATER_VOLUME: SensorEntityDescription(
        key=OBIS_WATER_VOLUME,
        translation_key="water_consumption",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
    ),
    OBIS_WATER_FLOW: SensorEntityDescription(
        key=OBIS_WATER_FLOW,
        translation_key="water_flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
}

# OBIS media (value group A) of a gas/water device per medium. The medium can
# be switched on the device at runtime, which switches the reported codes.
GW_OBIS_MEDIA: dict[Medium, frozenset[str]] = {
    Medium.GAS: frozenset({"7"}),
    Medium.WATER: frozenset({"8", "9"}),
}

OBIS_PHASE: dict[str, str] = {
    "36.7.0": "L1",
    "56.7.0": "L2",
    "76.7.0": "L3",
    "21.7.0": "L1",
    "41.7.0": "L2",
    "61.7.0": "L3",
    "22.7.0": "L1",
    "42.7.0": "L2",
    "62.7.0": "L3",
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
    UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR: (
        SensorDeviceClass.VOLUME_FLOW_RATE,
        SensorStateClass.MEASUREMENT,
    ),
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


# Device class of cumulative volume registers (m³) by OBIS medium (value
# group A): gas, cold water, hot water.
VOLUME_MEDIUM_DEVICE_CLASS: dict[str, SensorDeviceClass] = {
    "7": SensorDeviceClass.GAS,
    "8": SensorDeviceClass.WATER,
    "9": SensorDeviceClass.WATER,
}

ELECTRICITY_MEDIUM = "1"


def _split_obis(obis_code: str) -> tuple[str, list[str]]:
    """Split an OBIS code into its medium (value group A) and C.D.E parts.

    Electricity registers are reported in the short C.D.E form, other media
    in the full A-B:C.D.E form.
    """
    medium = ELECTRICITY_MEDIUM
    if ":" in obis_code:
        prefix, obis_code = obis_code.split(":", 1)
        medium = prefix.partition("-")[0]
    return medium, obis_code.split(".")


def _is_cumulative_register(obis_code: str) -> bool:
    """Return True for electricity x.8.y registers, the cumulative energy totals."""
    medium, parts = _split_obis(obis_code)
    return medium == ELECTRICITY_MEDIUM and len(parts) == 3 and parts[1] == "8"


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
    entity_registry = er.async_get(hass)
    known_obis_codes: set[str] = set()

    @callback
    def _async_remove_other_medium_entities() -> set[str]:
        """Remove the entities of the medium a gas/water device no longer meters.

        Returns the OBIS media of the other medium; their codes are not added.
        """
        meter = coordinator.data.meter
        # Only a gas/water device (``gw`` block) switches its medium. A meter
        # that reports several media keeps the entities of all of them.
        if meter.gw is None or meter.medium not in GW_OBIS_MEDIA:
            return set()
        other_media = {
            obis_medium
            for gw_medium, obis_media in GW_OBIS_MEDIA.items()
            if gw_medium is not meter.medium
            for obis_medium in obis_media
        }
        prefix = f"{coordinator.device_id}_"
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            obis_code = entity_entry.unique_id.removeprefix(prefix)
            if (
                entity_entry.domain == SENSOR_DOMAIN
                and entity_entry.unique_id.startswith(prefix)
                and ":" in obis_code
                and _split_obis(obis_code)[0] in other_media
            ):
                known_obis_codes.discard(obis_code)
                entity_registry.async_remove(entity_entry.entity_id)
        return other_media

    @callback
    def _async_add_obis_entities() -> None:
        """Add entities for OBIS codes not seen before.

        Registers that stop reporting keep their entity (e.g. a short telegram
        of an electricity meter); only a medium change of a gas/water device
        removes the entities of the previous medium.
        """
        other_media = _async_remove_other_medium_entities()
        entities: list[SensorEntity] = []
        for obis_code, obis_value in coordinator.data.meter.values.items():
            if obis_code in known_obis_codes or obis_code in METADATA_OBIS_CODES:
                continue
            if ":" in obis_code and _split_obis(obis_code)[0] in other_media:
                continue
            known_obis_codes.add(obis_code)
            if obis_code in KNOWN_OBIS_CODES:
                entities.append(
                    WattwaechterObisSensor(
                        coordinator=coordinator,
                        description=KNOWN_OBIS_CODES[obis_code],
                        obis_code=obis_code,
                    )
                )
            else:
                entities.append(
                    WattwaechterGenericObisSensor(coordinator, obis_code, obis_value)
                )
        if entities:
            async_add_entities(entities)

    _async_add_obis_entities()
    async_add_entities(
        WattwaechterDiagnosticSensor(coordinator, description)
        for description in DIAGNOSTIC_SENSORS
    )
    entry.async_on_unload(coordinator.async_add_listener(_async_add_obis_entities))


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

    @property
    @override
    def last_reset(self) -> datetime | None:
        """Return when the current meter reading started (gas/water volume).

        A meter exchange on the device sets it; the first reading entry and
        a correction of the reading keep it.
        """
        if self.entity_description.state_class is not SensorStateClass.TOTAL:
            return None
        if (gw := self.coordinator.data.meter.gw) is None:
            return None
        return gw.meter_since


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
        elif obis_value.unit == UnitOfVolume.CUBIC_METERS and (
            device_class := VOLUME_MEDIUM_DEVICE_CLASS.get(_split_obis(obis_code)[0])
        ):
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
