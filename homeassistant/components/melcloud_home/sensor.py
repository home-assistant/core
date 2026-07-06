"""Sensor platform for MELCloud Home."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiomelcloudhome import ATAUnit, ATWUnit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ATASensorEntityDescription(SensorEntityDescription):
    """Class to hold MELCloud Home ATA sensor description."""

    value_fn: Callable[[ATAUnit], StateType]


@dataclass(frozen=True, kw_only=True)
class ATWSensorEntityDescription(SensorEntityDescription):
    """Class to hold MELCloud Home ATW sensor description."""

    value_fn: Callable[[ATWUnit], StateType]
    exists_fn: Callable[[ATWUnit], bool] = lambda unit: True


ATA_SENSORS: tuple[ATASensorEntityDescription, ...] = (
    ATASensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit: unit.room_temperature,
    ),
    ATASensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda unit: unit.rssi,
    ),
)

ATW_SENSORS: tuple[ATWSensorEntityDescription, ...] = (
    ATWSensorEntityDescription(
        key="room_temperature_zone_1",
        translation_key="room_temperature_zone_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit: unit.room_temperature_zone1,
    ),
    ATWSensorEntityDescription(
        key="room_temperature_zone_2",
        translation_key="room_temperature_zone_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit: unit.room_temperature_zone2,
        exists_fn=lambda unit: bool(
            (unit.capabilities and unit.capabilities.has_zone2)
            or (unit.capabilities is None and unit.has_zone2)
        ),
    ),
    ATWSensorEntityDescription(
        key="tank_water_temperature",
        translation_key="tank_water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit: unit.tank_water_temperature,
    ),
    ATWSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda unit: unit.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home sensors."""
    coordinator = entry.runtime_data

    def _async_add_new_ata_units(units: list[ATAUnit]) -> None:
        async_add_entities(
            ATASensor(coordinator, entity_description, unit)
            for entity_description in ATA_SENSORS
            for unit in units
        )

    def _async_add_new_atw_units(units: list[ATWUnit]) -> None:
        async_add_entities(
            ATWSensor(coordinator, entity_description, unit)
            for entity_description in ATW_SENSORS
            for unit in units
            if entity_description.exists_fn(unit)
        )

    coordinator.new_ata_callbacks.append(_async_add_new_ata_units)
    coordinator.new_atw_callbacks.append(_async_add_new_atw_units)

    _async_add_new_ata_units(list(coordinator.ata_units.values()))
    _async_add_new_atw_units(list(coordinator.atw_units.values()))


class ATASensor(MelCloudHomeATAUnitEntity, SensorEntity):
    """Representation of a MELCloud Home ATA sensor."""

    entity_description: ATASensorEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATASensorEntityDescription,
        unit: ATAUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.unit)


class ATWSensor(MelCloudHomeATWUnitEntity, SensorEntity):
    """Representation of a MELCloud Home ATW sensor."""

    entity_description: ATWSensorEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATWSensorEntityDescription,
        unit: ATWUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.unit)
