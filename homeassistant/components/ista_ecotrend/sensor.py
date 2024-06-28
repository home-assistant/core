"""Sensor platform for Ista EcoTrend integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IstaConfigEntry
from .const import DOMAIN
from .coordinator import IstaCoordinator
from .util import IstaConsumptionType, IstaValueType, get_native_value

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class IstaSensorEntityDescription(SensorEntityDescription):
    """Ista EcoTrend Sensor Description."""

    consumption_type: IstaConsumptionType
    value_type: IstaValueType | None = None


class IstaSensorEntity(StrEnum):
    """Ista EcoTrend Entities."""

    HEATING = "heating"
    HEATING_ENERGY = "heating_energy"
    HEATING_COST = "heating_cost"

    HOT_WATER = "hot_water"
    HOT_WATER_ENERGY = "hot_water_energy"
    HOT_WATER_COST = "hot_water_cost"

    WATER = "water"
    WATER_COST = "water_cost"


SENSOR_DESCRIPTIONS: tuple[IstaSensorEntityDescription, ...] = (
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HEATING,
        translation_key=IstaSensorEntity.HEATING,
        suggested_display_precision=0,
        consumption_type=IstaConsumptionType.HEATING,
        native_unit_of_measurement="units",
        state_class=SensorStateClass.TOTAL,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HEATING_ENERGY,
        translation_key=IstaSensorEntity.HEATING_ENERGY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        consumption_type=IstaConsumptionType.HEATING,
        value_type=IstaValueType.ENERGY,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HEATING_COST,
        translation_key=IstaSensorEntity.HEATING_COST,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.HEATING,
        value_type=IstaValueType.COSTS,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HOT_WATER,
        translation_key=IstaSensorEntity.HOT_WATER,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        consumption_type=IstaConsumptionType.HOT_WATER,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HOT_WATER_ENERGY,
        translation_key=IstaSensorEntity.HOT_WATER_ENERGY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        consumption_type=IstaConsumptionType.HOT_WATER,
        value_type=IstaValueType.ENERGY,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.HOT_WATER_COST,
        translation_key=IstaSensorEntity.HOT_WATER_COST,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.HOT_WATER,
        value_type=IstaValueType.COSTS,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.WATER,
        translation_key=IstaSensorEntity.WATER,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.WATER,
    ),
    IstaSensorEntityDescription(
        key=IstaSensorEntity.WATER_COST,
        translation_key=IstaSensorEntity.WATER_COST,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        consumption_type=IstaConsumptionType.WATER,
        value_type=IstaValueType.COSTS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IstaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ista EcoTrend sensors."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        IstaSensor(coordinator, description, consumption_unit)
        for description in SENSOR_DESCRIPTIONS
        for consumption_unit in coordinator.data
    )


class IstaSensor(CoordinatorEntity[IstaCoordinator], SensorEntity):
    """Ista EcoTrend sensor."""

    entity_description: IstaSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IstaCoordinator,
        entity_description: IstaSensorEntityDescription,
        consumption_unit: str,
    ) -> None:
        """Initialize the ista EcoTrend sensor."""
        super().__init__(coordinator)
        self.consumption_unit = consumption_unit
        self.entity_description = entity_description
        self._attr_unique_id = f"{consumption_unit}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ista SE",
            model="ista EcoTrend",
            name=f"{coordinator.details[consumption_unit]["address"]["street"]} "
            f"{coordinator.details[consumption_unit]["address"]["houseNumber"]}".strip(),
            configuration_url="https://ecotrend.ista.de/",
            identifiers={(DOMAIN, consumption_unit)},
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""

        return get_native_value(
            data=self.coordinator.data[self.consumption_unit],
            consumption_type=self.entity_description.consumption_type,
            value_type=self.entity_description.value_type,
        )
