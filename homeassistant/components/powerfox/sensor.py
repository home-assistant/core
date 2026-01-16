"""Sensors for Powerfox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from powerfox import Device, GasReport, HeatMeter, PowerMeter, WaterMeter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy, UnitOfPower, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    PowerfoxBaseCoordinator,
    PowerfoxConfigEntry,
    PowerfoxDataUpdateCoordinator,
    PowerfoxReportDataUpdateCoordinator,
)
from .entity import PowerfoxEntity


@dataclass(frozen=True, kw_only=True)
class PowerfoxSensorEntityDescription[T: (PowerMeter, WaterMeter, HeatMeter)](
    SensorEntityDescription
):
    """Describes Poweropti sensor entity."""

    value_fn: Callable[[T], float | int | None]


@dataclass(frozen=True, kw_only=True)
class PowerfoxReportSensorEntityDescription(SensorEntityDescription):
    """Describes Powerfox report sensor entity."""

    value_fn: Callable[[GasReport], float | int | None]


SENSORS_POWER: tuple[PowerfoxSensorEntityDescription[PowerMeter], ...] = (
    PowerfoxSensorEntityDescription[PowerMeter](
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.power,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage",
        translation_key="energy_usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage_low_tariff",
        translation_key="energy_usage_low_tariff",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_low_tariff,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_usage_high_tariff",
        translation_key="energy_usage_high_tariff",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_usage_high_tariff,
    ),
    PowerfoxSensorEntityDescription[PowerMeter](
        key="energy_return",
        translation_key="energy_return",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.energy_return,
    ),
)


SENSORS_WATER: tuple[PowerfoxSensorEntityDescription[WaterMeter], ...] = (
    PowerfoxSensorEntityDescription[WaterMeter](
        key="cold_water",
        translation_key="cold_water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.cold_water,
    ),
    PowerfoxSensorEntityDescription[WaterMeter](
        key="warm_water",
        translation_key="warm_water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.warm_water,
    ),
)

SENSORS_HEAT: tuple[PowerfoxSensorEntityDescription[HeatMeter], ...] = (
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_total_energy",
        translation_key="heat_total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.total_energy,
    ),
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_delta_energy",
        translation_key="heat_delta_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda meter: meter.delta_energy,
    ),
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_total_volume",
        translation_key="heat_total_volume",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda meter: meter.total_volume,
    ),
    PowerfoxSensorEntityDescription[HeatMeter](
        key="heat_delta_volume",
        translation_key="heat_delta_volume",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda meter: meter.delta_volume,
    ),
)

SENSORS_GAS: tuple[PowerfoxReportSensorEntityDescription, ...] = (
    PowerfoxReportSensorEntityDescription(
        key="gas_consumption_today",
        translation_key="gas_consumption_today",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda gas: gas.sum,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_consumption_energy_today",
        translation_key="gas_consumption_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda gas: gas.consumption_kwh,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_current_consumption",
        translation_key="gas_current_consumption",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        value_fn=lambda gas: gas.current_consumption,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_current_consumption_energy",
        translation_key="gas_current_consumption_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        value_fn=lambda gas: gas.current_consumption_kwh,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_cost_today",
        translation_key="gas_cost_today",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda gas: gas.sum_currency,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_max_consumption_today",
        translation_key="gas_max_consumption_today",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        value_fn=lambda gas: gas.max_consumption,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_min_consumption_today",
        translation_key="gas_min_consumption_today",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        value_fn=lambda gas: gas.min_consumption,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_avg_consumption_today",
        translation_key="gas_avg_consumption_today",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        entity_registry_enabled_default=False,
        value_fn=lambda gas: gas.avg_consumption,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_max_consumption_energy_today",
        translation_key="gas_max_consumption_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        value_fn=lambda gas: gas.max_consumption_kwh,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_min_consumption_energy_today",
        translation_key="gas_min_consumption_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        value_fn=lambda gas: gas.min_consumption_kwh,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_avg_consumption_energy_today",
        translation_key="gas_avg_consumption_energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        value_fn=lambda gas: gas.avg_consumption_kwh,
    ),
    PowerfoxReportSensorEntityDescription(
        key="gas_max_cost_today",
        translation_key="gas_max_cost_today",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        value_fn=lambda gas: gas.max_currency,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerfoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Powerfox sensors based on a config entry."""
    entities: list[SensorEntity] = []
    for coordinator in entry.runtime_data:
        if isinstance(coordinator, PowerfoxReportDataUpdateCoordinator):
            gas_report = coordinator.data.gas
            if gas_report is None:
                continue
            entities.extend(
                PowerfoxGasSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_GAS
                if description.value_fn(gas_report) is not None
            )
            continue
        if isinstance(coordinator.data, PowerMeter):
            entities.extend(
                PowerfoxSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_POWER
                if description.value_fn(coordinator.data) is not None
            )
        if isinstance(coordinator.data, WaterMeter):
            entities.extend(
                PowerfoxSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_WATER
            )
        if isinstance(coordinator.data, HeatMeter):
            entities.extend(
                PowerfoxSensorEntity(
                    coordinator=coordinator,
                    description=description,
                    device=coordinator.device,
                )
                for description in SENSORS_HEAT
            )
    async_add_entities(entities)


class BasePowerfoxSensorEntity[CoordinatorT: PowerfoxBaseCoordinator[Any]](
    PowerfoxEntity[CoordinatorT], SensorEntity
):
    """Common base for Powerfox sensor entities."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: CoordinatorT,
        device: Device,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the shared Powerfox sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"


class PowerfoxSensorEntity(BasePowerfoxSensorEntity[PowerfoxDataUpdateCoordinator]):
    """Defines a powerfox poweropti sensor."""

    coordinator: PowerfoxDataUpdateCoordinator
    entity_description: PowerfoxSensorEntityDescription

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self.coordinator.data)


class PowerfoxGasSensorEntity(
    BasePowerfoxSensorEntity[PowerfoxReportDataUpdateCoordinator]
):
    """Defines a powerfox gas meter sensor."""

    coordinator: PowerfoxReportDataUpdateCoordinator
    entity_description: PowerfoxReportSensorEntityDescription

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the entity."""
        gas_report = self.coordinator.data.gas
        if TYPE_CHECKING:
            assert gas_report is not None
        return self.entity_description.value_fn(gas_report)
