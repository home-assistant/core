"""Sensor platform for the WattWächter Plus integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WattwaechterConfigEntry
from .coordinator import WattwaechterCoordinator
from .entity import WattwaechterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ObisSensorDescription(SensorEntityDescription):
    """Describes a WattWächter OBIS sensor."""


@dataclass(frozen=True, kw_only=True)
class DiagnosticSensorDescription(SensorEntityDescription):
    """Describes a WattWächter diagnostic sensor."""

    system_section: str
    system_key: str


KNOWN_OBIS_CODES: dict[str, ObisSensorDescription] = {
    # Energy meters (kWh) - total_increasing
    "1.8.0": ObisSensorDescription(
        key="1.8.0",
        translation_key="import_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "2.8.0": ObisSensorDescription(
        key="2.8.0",
        translation_key="export_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "1.8.1": ObisSensorDescription(
        key="1.8.1",
        translation_key="import_tariff_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "1.8.2": ObisSensorDescription(
        key="1.8.2",
        translation_key="import_tariff_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "2.8.1": ObisSensorDescription(
        key="2.8.1",
        translation_key="export_tariff_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    "2.8.2": ObisSensorDescription(
        key="2.8.2",
        translation_key="export_tariff_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    # Power (W) - measurement
    "16.7.0": ObisSensorDescription(
        key="16.7.0",
        translation_key="active_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "36.7.0": ObisSensorDescription(
        key="36.7.0",
        translation_key="active_power_l1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "56.7.0": ObisSensorDescription(
        key="56.7.0",
        translation_key="active_power_l2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "76.7.0": ObisSensorDescription(
        key="76.7.0",
        translation_key="active_power_l3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    # Voltage (V) - measurement
    "32.7.0": ObisSensorDescription(
        key="32.7.0",
        translation_key="voltage_l1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "52.7.0": ObisSensorDescription(
        key="52.7.0",
        translation_key="voltage_l2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "72.7.0": ObisSensorDescription(
        key="72.7.0",
        translation_key="voltage_l3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    # Current (A) - measurement
    "31.7.0": ObisSensorDescription(
        key="31.7.0",
        translation_key="current_l1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "51.7.0": ObisSensorDescription(
        key="51.7.0",
        translation_key="current_l2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "71.7.0": ObisSensorDescription(
        key="71.7.0",
        translation_key="current_l3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    # Frequency (Hz) - measurement
    "14.7.0": ObisSensorDescription(
        key="14.7.0",
        translation_key="frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    # Power factor - measurement
    "13.7.0": ObisSensorDescription(
        key="13.7.0",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "33.7.0": ObisSensorDescription(
        key="33.7.0",
        translation_key="power_factor_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "53.7.0": ObisSensorDescription(
        key="53.7.0",
        translation_key="power_factor_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    "73.7.0": ObisSensorDescription(
        key="73.7.0",
        translation_key="power_factor_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
}

DIAGNOSTIC_SENSORS: tuple[DiagnosticSensorDescription, ...] = (
    DiagnosticSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        system_section="wifi",
        system_key="signal_strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DiagnosticSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        system_section="wifi",
        system_key="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DiagnosticSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        system_section="wifi",
        system_key="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DiagnosticSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        system_section="esp",
        system_key="os_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DiagnosticSensorDescription(
        key="mdns_name",
        translation_key="mdns_name",
        system_section="wifi",
        system_key="mdns_name",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Map API unit strings to HA unit/device_class/state_class/precision for unknown OBIS codes
UNIT_MAP: dict[str, tuple[str | None, SensorDeviceClass | None, SensorStateClass | None, int | None]] = {
    "kWh": ("kWh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, 2),
    "Wh": ("Wh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, 0),
    "W": ("W", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, 0),
    "V": ("V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, 1),
    "A": ("A", SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, 2),
    "Hz": ("Hz", SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, 2),
    "var": ("var", None, SensorStateClass.MEASUREMENT, 0),
    "VA": ("VA", None, SensorStateClass.MEASUREMENT, 0),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattwaechterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WattWächter sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    # Dynamic OBIS sensors from meter data
    if coordinator.data.meter:
        for obis_code, obis_value in coordinator.data.meter.values.items():
            if obis_code in KNOWN_OBIS_CODES:
                # Known OBIS code with predefined metadata
                entities.append(
                    WattwaechterObisSensor(
                        coordinator=coordinator,
                        description=KNOWN_OBIS_CODES[obis_code],
                        obis_code=obis_code,
                    )
                )
            else:
                # Unknown OBIS code - create generic sensor from API data
                api_unit = obis_value.unit
                value = obis_value.value
                is_numeric = isinstance(value, (int, float))

                if api_unit and api_unit in UNIT_MAP:
                    unit, device_class, state_class, precision = UNIT_MAP[api_unit]
                elif is_numeric:
                    unit = api_unit or None
                    device_class = None
                    state_class = SensorStateClass.MEASUREMENT
                    precision = None
                else:
                    # String values (e.g. meter number, manufacturer code)
                    unit = None
                    device_class = None
                    state_class = None
                    precision = None

                description = ObisSensorDescription(
                    key=obis_code,
                    name=f"OBIS {obis_code}",
                    native_unit_of_measurement=unit,
                    device_class=device_class,
                    state_class=state_class,
                    suggested_display_precision=precision,
                )
                entities.append(
                    WattwaechterObisSensor(
                        coordinator=coordinator,
                        description=description,
                        obis_code=obis_code,
                    )
                )

    # Diagnostic sensors from system info
    if coordinator.data.system:
        for diag_description in DIAGNOSTIC_SENSORS:
            entities.append(
                WattwaechterDiagnosticSensor(
                    coordinator=coordinator,
                    description=diag_description,
                )
            )

    async_add_entities(entities)


class WattwaechterObisSensor(WattwaechterEntity, SensorEntity):
    """Sensor for OBIS meter values."""

    entity_description: ObisSensorDescription

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        description: ObisSensorDescription,
        obis_code: str,
    ) -> None:
        """Initialize the OBIS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._obis_code = obis_code
        self._attr_unique_id = f"{coordinator.device_id}_{obis_code}"

    @property
    def native_value(self) -> float | str | None:
        """Return the current sensor value."""
        if self.coordinator.data.meter is None:
            return None
        obis = self.coordinator.data.meter.values.get(self._obis_code)
        if obis is None:
            return None
        return obis.value


class WattwaechterDiagnosticSensor(WattwaechterEntity, SensorEntity):
    """Sensor for diagnostic system information."""

    entity_description: DiagnosticSensorDescription

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        description: DiagnosticSensorDescription,
    ) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> str | float | None:
        """Return the current sensor value."""
        system = self.coordinator.data.system
        if not system:
            return None
        return system.get_value(
            self.entity_description.system_section,
            self.entity_description.system_key,
        )
