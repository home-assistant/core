"""Support for powerwall sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from tesla_powerwall import GridState, MeterResponse, MeterType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, POWERWALL_COORDINATOR
from .entity import BatteryEntity, PowerWallEntity
from .models import BatteryResponse, PowerwallRuntimeData

_METER_DIRECTION_EXPORT = "export"
_METER_DIRECTION_IMPORT = "import"

_ValueParamT = TypeVar("_ValueParamT")
_ValueT = TypeVar("_ValueT", bound=float | int | str)


@dataclass(frozen=True)
class PowerwallRequiredKeysMixin(Generic[_ValueParamT, _ValueT]):
    """Mixin for required keys."""

    value_fn: Callable[[_ValueParamT], _ValueT]


@dataclass(frozen=True)
class PowerwallSensorEntityDescription(
    SensorEntityDescription,
    PowerwallRequiredKeysMixin[_ValueParamT, _ValueT],
    Generic[_ValueParamT, _ValueT],
):
    """Describes Powerwall entity."""


def _get_meter_power(meter: MeterResponse) -> float:
    """Get the current value in kW."""
    return meter.get_power(precision=3)


def _get_meter_frequency(meter: MeterResponse) -> float:
    """Get the current value in Hz."""
    return round(meter.frequency, 1)


def _get_meter_total_current(meter: MeterResponse) -> float:
    """Get the current value in A."""
    return meter.get_instant_total_current()


def _get_meter_average_voltage(meter: MeterResponse) -> float:
    """Get the current value in V."""
    return round(meter.instant_average_voltage, 1)


POWERWALL_INSTANT_SENSORS = (
    PowerwallSensorEntityDescription[MeterResponse, float](
        key="instant_power",
        translation_key="instant_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=_get_meter_power,
    ),
    PowerwallSensorEntityDescription[MeterResponse, float](
        key="instant_frequency",
        translation_key="instant_frequency",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_frequency,
    ),
    PowerwallSensorEntityDescription[MeterResponse, float](
        key="instant_current",
        translation_key="instant_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_total_current,
    ),
    PowerwallSensorEntityDescription[MeterResponse, float](
        key="instant_voltage",
        translation_key="instant_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_average_voltage,
    ),
)


BATTERY_INSTANT_SENSORS: list[PowerwallSensorEntityDescription] = [
    PowerwallSensorEntityDescription[BatteryResponse, int](
        key="battery_capacity",
        translation_key="battery_capacity",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda battery_data: battery_data.capacity,
    ),
    PowerwallSensorEntityDescription[BatteryResponse, float](
        key="battery_instant_voltage",
        translation_key="battery_instant_voltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda battery_data: round(battery_data.v_out, 1),
    ),
    PowerwallSensorEntityDescription[BatteryResponse, float](
        key="instant_frequency",
        translation_key="instant_frequency",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_registry_enabled_default=False,
        value_fn=lambda battery_data: round(battery_data.f_out, 1),
    ),
    PowerwallSensorEntityDescription[BatteryResponse, float](
        key="instant_current",
        translation_key="instant_current",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
        value_fn=lambda battery_data: round(battery_data.i_out, 1),
    ),
    PowerwallSensorEntityDescription[BatteryResponse, int](
        key="instant_power",
        translation_key="instant_power",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda battery_data: battery_data.p_out,
    ),
    PowerwallSensorEntityDescription[BatteryResponse, float](
        key="battery_export",
        translation_key="battery_export",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda battery_data: battery_data.energy_discharged,
    ),
    PowerwallSensorEntityDescription[BatteryResponse, float](
        key="battery_import",
        translation_key="battery_import",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=0,
        value_fn=lambda battery_data: battery_data.energy_charged,
    ),
    PowerwallSensorEntityDescription[BatteryResponse, int](
        key="battery_remaining",
        translation_key="battery_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda battery_data: battery_data.energy_remaining,
    ),
    PowerwallSensorEntityDescription[BatteryResponse, str](
        key="grid_state",
        translation_key="grid_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[state.value.lower() for state in GridState],
        value_fn=lambda battery_data: battery_data.grid_state.value.lower(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the powerwall sensors."""
    powerwall_data: PowerwallRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    assert coordinator is not None
    data = coordinator.data
    entities: list[Entity] = [
        PowerWallChargeSensor(powerwall_data),
    ]

    if data.backup_reserve is not None:
        entities.append(PowerWallBackupReserveSensor(powerwall_data))

    for meter in data.meters.meters:
        entities.append(PowerWallExportSensor(powerwall_data, meter))
        entities.append(PowerWallImportSensor(powerwall_data, meter))
        entities.extend(
            PowerWallEnergySensor(powerwall_data, meter, description)
            for description in POWERWALL_INSTANT_SENSORS
        )

    for battery in data.batteries.values():
        entities.extend(
            PowerWallBatterySensor(powerwall_data, battery, description)
            for description in BATTERY_INSTANT_SENSORS
        )

    async_add_entities(entities)


class PowerWallChargeSensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall charge sensor."""

    _attr_translation_key = "charge"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_charge"

    @property
    def native_value(self) -> int:
        """Get the current value in percentage."""
        return round(self.data.charge)


class PowerWallEnergySensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall Energy sensor."""

    entity_description: PowerwallSensorEntityDescription[MeterResponse, float]

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
        description: PowerwallSensorEntityDescription[MeterResponse, float],
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(powerwall_data)
        self._meter = meter
        self._attr_translation_key = f"{meter.value}_{description.translation_key}"
        self._attr_unique_id = f"{self.base_unique_id}_{meter.value}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Get the current value."""
        meter = self.data.meters.get_meter(self._meter)
        if meter is not None:
            return self.entity_description.value_fn(meter)

        return None


class PowerWallBackupReserveSensor(PowerWallEntity, SensorEntity):
    """Representation of the Powerwall backup reserve setting."""

    _attr_translation_key = "backup_reserve"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_backup_reserve"

    @property
    def native_value(self) -> int | None:
        """Get the current value in percentage."""
        if self.data.backup_reserve is None:
            return None
        return round(self.data.backup_reserve)


class PowerWallEnergyDirectionSensor(PowerWallEntity, SensorEntity):
    """Representation of an Powerwall Direction Energy sensor."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
        meter_direction: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self._meter = meter
        self._attr_translation_key = f"{meter.value}_{meter_direction}"
        self._attr_unique_id = f"{self.base_unique_id}_{meter.value}_{meter_direction}"

    @property
    def available(self) -> bool:
        """Check if the reading is actually available.

        The device reports 0 when something goes wrong which
        we do not want to include in statistics and its a
        transient data error.
        """
        return super().available and self.meter is not None

    @property
    def meter(self) -> MeterResponse | None:
        """Get the meter for the sensor."""
        return self.data.meters.get_meter(self._meter)


class PowerWallExportSensor(PowerWallEnergyDirectionSensor):
    """Representation of an Powerwall Export sensor."""

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data, meter, _METER_DIRECTION_EXPORT)

    @property
    def native_value(self) -> float | None:
        """Get the current value in kWh."""
        meter = self.meter
        if TYPE_CHECKING:
            assert meter is not None
        return meter.get_energy_exported()


class PowerWallImportSensor(PowerWallEnergyDirectionSensor):
    """Representation of an Powerwall Import sensor."""

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        meter: MeterType,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data, meter, _METER_DIRECTION_IMPORT)

    @property
    def native_value(self) -> float | None:
        """Get the current value in kWh."""
        meter = self.meter
        if TYPE_CHECKING:
            assert meter is not None
        return meter.get_energy_imported()


class PowerWallBatterySensor(BatteryEntity, SensorEntity, Generic[_ValueT]):
    """Representation of an Powerwall Battery sensor."""

    entity_description: PowerwallSensorEntityDescription[BatteryResponse, _ValueT]

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        battery: BatteryResponse,
        description: PowerwallSensorEntityDescription[BatteryResponse, _ValueT],
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(powerwall_data, battery)
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{self.base_unique_id}_{description.key}"

    @property
    def native_value(self) -> float | int | str:
        """Get the current value."""
        return self.entity_description.value_fn(self.battery_data)
