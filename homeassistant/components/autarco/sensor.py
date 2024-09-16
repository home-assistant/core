"""Support for Autarco sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from autarco import Battery, Inverter, Solar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutarcoConfigEntry
from .const import DOMAIN
from .coordinator import AutarcoDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AutarcoBatterySensorEntityDescription(SensorEntityDescription):
    """Describes an Autarco sensor entity."""

    value_fn: Callable[[Battery], StateType]


SENSORS_BATTERY: tuple[AutarcoBatterySensorEntityDescription, ...] = (
    AutarcoBatterySensorEntityDescription(
        key="flow_now",
        translation_key="flow_now",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda battery: battery.flow_now,
    ),
    AutarcoBatterySensorEntityDescription(
        key="state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda battery: battery.state_of_charge,
    ),
    AutarcoBatterySensorEntityDescription(
        key="discharged_today",
        translation_key="discharged_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda battery: battery.discharged_today,
    ),
    AutarcoBatterySensorEntityDescription(
        key="discharged_month",
        translation_key="discharged_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda battery: battery.discharged_month,
    ),
    AutarcoBatterySensorEntityDescription(
        key="discharged_total",
        translation_key="discharged_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.discharged_total,
    ),
    AutarcoBatterySensorEntityDescription(
        key="charged_today",
        translation_key="charged_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda battery: battery.charged_today,
    ),
    AutarcoBatterySensorEntityDescription(
        key="charged_month",
        translation_key="charged_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda battery: battery.charged_month,
    ),
    AutarcoBatterySensorEntityDescription(
        key="charged_total",
        translation_key="charged_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda battery: battery.charged_total,
    ),
)


@dataclass(frozen=True, kw_only=True)
class AutarcoSolarSensorEntityDescription(SensorEntityDescription):
    """Describes an Autarco sensor entity."""

    value_fn: Callable[[Solar], StateType]


SENSORS_SOLAR: tuple[AutarcoSolarSensorEntityDescription, ...] = (
    AutarcoSolarSensorEntityDescription(
        key="power_production",
        translation_key="power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda solar: solar.power_production,
    ),
    AutarcoSolarSensorEntityDescription(
        key="energy_production_today",
        translation_key="energy_production_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda solar: solar.energy_production_today,
    ),
    AutarcoSolarSensorEntityDescription(
        key="energy_production_month",
        translation_key="energy_production_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda solar: solar.energy_production_month,
    ),
    AutarcoSolarSensorEntityDescription(
        key="energy_production_total",
        translation_key="energy_production_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda solar: solar.energy_production_total,
    ),
)


@dataclass(frozen=True, kw_only=True)
class AutarcoInverterSensorEntityDescription(SensorEntityDescription):
    """Describes an Autarco inverter sensor entity."""

    value_fn: Callable[[Inverter], StateType]


SENSORS_INVERTER: tuple[AutarcoInverterSensorEntityDescription, ...] = (
    AutarcoInverterSensorEntityDescription(
        key="out_ac_power",
        translation_key="out_ac_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda inverter: inverter.out_ac_power,
    ),
    AutarcoInverterSensorEntityDescription(
        key="out_ac_energy_total",
        translation_key="out_ac_energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda inverter: inverter.out_ac_energy_total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutarcoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Autarco sensors based on a config entry."""
    entities: list[SensorEntity] = []
    for coordinator in entry.runtime_data:
        entities.extend(
            AutarcoSolarSensorEntity(
                coordinator=coordinator,
                description=description,
            )
            for description in SENSORS_SOLAR
        )
        entities.extend(
            AutarcoInverterSensorEntity(
                coordinator=coordinator,
                description=description,
                serial_number=inverter,
            )
            for description in SENSORS_INVERTER
            for inverter in coordinator.data.inverters
        )
        if coordinator.data.battery:
            entities.extend(
                AutarcoBatterySensorEntity(
                    coordinator=coordinator,
                    description=description,
                )
                for description in SENSORS_BATTERY
            )
    async_add_entities(entities)


class AutarcoBatterySensorEntity(
    CoordinatorEntity[AutarcoDataUpdateCoordinator], SensorEntity
):
    """Defines an Autarco battery sensor."""

    entity_description: AutarcoBatterySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: AutarcoDataUpdateCoordinator,
        description: AutarcoBatterySensorEntityDescription,
    ) -> None:
        """Initialize Autarco sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.account_site.site_id}_battery_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.account_site.site_id}_battery")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Autarco",
            name="Battery",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        assert self.coordinator.data.battery is not None
        return self.entity_description.value_fn(self.coordinator.data.battery)


class AutarcoSolarSensorEntity(
    CoordinatorEntity[AutarcoDataUpdateCoordinator], SensorEntity
):
    """Defines an Autarco solar sensor."""

    entity_description: AutarcoSolarSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: AutarcoDataUpdateCoordinator,
        description: AutarcoSolarSensorEntityDescription,
    ) -> None:
        """Initialize Autarco sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.account_site.site_id}_solar_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.account_site.site_id}_solar")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Autarco",
            name="Solar",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.solar)


class AutarcoInverterSensorEntity(
    CoordinatorEntity[AutarcoDataUpdateCoordinator], SensorEntity
):
    """Defines an Autarco inverter sensor."""

    entity_description: AutarcoInverterSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: AutarcoDataUpdateCoordinator,
        description: AutarcoInverterSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize Autarco sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Inverter {serial_number}",
            manufacturer="Autarco",
            model="Inverter",
            serial_number=serial_number,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data.inverters[self._serial_number]
        )
