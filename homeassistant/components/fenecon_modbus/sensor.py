"""Sensor platform for the Fenecon Modbus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import override

from fenecon_modbus import FeneconData, GridMode, State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import FeneconConfigEntry, FeneconCoordinator
from .entity import FeneconEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FeneconSensorEntityDescription(SensorEntityDescription):
    """Describes a Fenecon sensor entity."""

    value_fn: Callable[[FeneconData], StateType | datetime]


def _power(
    key: str,
    value_fn: Callable[[FeneconData], float | None],
    *,
    enabled: bool = True,
) -> FeneconSensorEntityDescription:
    return FeneconSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_fn=value_fn,
    )


def _peak_power(
    key: str, value_fn: Callable[[FeneconData], float | None]
) -> FeneconSensorEntityDescription:
    return FeneconSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=value_fn,
    )


def _energy(
    key: str, value_fn: Callable[[FeneconData], float | None]
) -> FeneconSensorEntityDescription:
    return FeneconSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=value_fn,
    )


def _enum_option(value: State | GridMode | None) -> str | None:
    return value.name.lower() if value is not None else None


SENSORS: tuple[FeneconSensorEntityDescription, ...] = (
    FeneconSensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.name.lower() for state in State],
        value_fn=lambda data: _enum_option(data.state),
    ),
    FeneconSensorEntityDescription(
        key="grid_mode",
        translation_key="grid_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[mode.name.lower() for mode in GridMode],
        value_fn=lambda data: _enum_option(data.grid_mode),
    ),
    FeneconSensorEntityDescription(
        key="ess_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.ess_soc,
    ),
    FeneconSensorEntityDescription(
        key="ess_capacity",
        translation_key="ess_capacity",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.ess_capacity,
    ),
    _power("ess_active_power", lambda data: data.ess_active_power),
    _power("ess_discharge_power", lambda data: data.ess_discharge_power),
    FeneconSensorEntityDescription(
        key="ess_reactive_power",
        translation_key="ess_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.ess_reactive_power,
    ),
    _power("grid_active_power", lambda data: data.grid_active_power),
    _power("production_active_power", lambda data: data.production_active_power),
    _power("production_ac_active_power", lambda data: data.production_ac_active_power),
    _power("production_dc_actual_power", lambda data: data.production_dc_actual_power),
    _power("consumption_active_power", lambda data: data.consumption_active_power),
    _power("ess_active_power_l1", lambda data: data.ess_active_power_l1, enabled=False),
    _power("ess_active_power_l2", lambda data: data.ess_active_power_l2, enabled=False),
    _power("ess_active_power_l3", lambda data: data.ess_active_power_l3, enabled=False),
    _power(
        "grid_active_power_l1", lambda data: data.grid_active_power_l1, enabled=False
    ),
    _power(
        "grid_active_power_l2", lambda data: data.grid_active_power_l2, enabled=False
    ),
    _power(
        "grid_active_power_l3", lambda data: data.grid_active_power_l3, enabled=False
    ),
    _power(
        "production_ac_active_power_l1",
        lambda data: data.production_ac_active_power_l1,
        enabled=False,
    ),
    _power(
        "production_ac_active_power_l2",
        lambda data: data.production_ac_active_power_l2,
        enabled=False,
    ),
    _power(
        "production_ac_active_power_l3",
        lambda data: data.production_ac_active_power_l3,
        enabled=False,
    ),
    _power(
        "consumption_active_power_l1",
        lambda data: data.consumption_active_power_l1,
        enabled=False,
    ),
    _power(
        "consumption_active_power_l2",
        lambda data: data.consumption_active_power_l2,
        enabled=False,
    ),
    _power(
        "consumption_active_power_l3",
        lambda data: data.consumption_active_power_l3,
        enabled=False,
    ),
    _peak_power("grid_min_active_power", lambda data: data.grid_min_active_power),
    _peak_power("grid_max_active_power", lambda data: data.grid_max_active_power),
    _peak_power(
        "production_max_active_power", lambda data: data.production_max_active_power
    ),
    _peak_power(
        "consumption_max_active_power",
        lambda data: data.consumption_max_active_power,
    ),
    _energy("ess_active_charge_energy", lambda data: data.ess_active_charge_energy),
    _energy(
        "ess_active_discharge_energy", lambda data: data.ess_active_discharge_energy
    ),
    _energy("ess_dc_charge_energy", lambda data: data.ess_dc_charge_energy),
    _energy("ess_dc_discharge_energy", lambda data: data.ess_dc_discharge_energy),
    _energy("grid_buy_active_energy", lambda data: data.grid_buy_active_energy),
    _energy("grid_sell_active_energy", lambda data: data.grid_sell_active_energy),
    _energy("production_active_energy", lambda data: data.production_active_energy),
    _energy(
        "production_ac_active_energy", lambda data: data.production_ac_active_energy
    ),
    _energy(
        "production_dc_active_energy", lambda data: data.production_dc_active_energy
    ),
    _energy("consumption_active_energy", lambda data: data.consumption_active_energy),
    FeneconSensorEntityDescription(
        key="grid_mode_off_grid_time",
        translation_key="grid_mode_off_grid_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.grid_mode_off_grid_time,
    ),
    FeneconSensorEntityDescription(
        key="system_time",
        translation_key="system_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            datetime.fromtimestamp(data.system_time_utc, UTC)
            if data.system_time_utc is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FeneconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fenecon sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        FeneconSensor(coordinator, description) for description in SENSORS
    )


class FeneconSensor(FeneconEntity, SensorEntity):
    """Representation of a Fenecon sensor."""

    entity_description: FeneconSensorEntityDescription

    def __init__(
        self,
        coordinator: FeneconCoordinator,
        description: FeneconSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
