"""Sensor platform for MELCloud Home."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
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
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from .common import async_setup_unit_entities
from .coordinator import (
    MelCloudHomeConfigEntry,
    MelCloudHomeCoordinator,
    MelCloudHomeEnergyCoordinator,
)
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 0

ENERGY_CONSUMED_DESCRIPTION = SensorEntityDescription(
    key="energy_consumed",
    translation_key="energy_consumed",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL,
    native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
)


def _has_energy_meter(unit: ATAUnit | ATWUnit) -> bool:
    """Return whether a unit reports an energy consumption meter."""
    return bool(unit.capabilities and unit.capabilities.has_energy_consumed_meter)


@dataclass(frozen=True, kw_only=True)
class MelCloudHomeSensorEntityDescription[_UnitT: ATAUnit | ATWUnit](
    SensorEntityDescription
):
    """Class to hold MELCloud Home sensor description."""

    value_fn: Callable[[_UnitT, MelCloudHomeCoordinator], StateType]
    exists_fn: Callable[[_UnitT], bool] = lambda _: True


def _common_sensor_descriptions[_UnitT: ATAUnit | ATWUnit](
    unit_type: type[_UnitT],
) -> tuple[MelCloudHomeSensorEntityDescription[_UnitT], ...]:
    """Return the sensor descriptions shared by ATA and ATW units."""
    return (
        MelCloudHomeSensorEntityDescription(
            key="rssi",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=lambda unit, _: unit.rssi,
        ),
    )


ATA_SENSORS: tuple[MelCloudHomeSensorEntityDescription[ATAUnit], ...] = (
    MelCloudHomeSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit, _: unit.room_temperature,
    ),
    *_common_sensor_descriptions(ATAUnit),
)

ATW_SENSORS: tuple[MelCloudHomeSensorEntityDescription[ATWUnit], ...] = (
    MelCloudHomeSensorEntityDescription(
        key="room_temperature_zone_1",
        translation_key="room_temperature_zone_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit, _: unit.room_temperature_zone1,
    ),
    MelCloudHomeSensorEntityDescription(
        key="room_temperature_zone_2",
        translation_key="room_temperature_zone_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit, _: unit.room_temperature_zone2,
        exists_fn=lambda unit: bool(
            (unit.capabilities and unit.capabilities.has_zone2)
            or (unit.capabilities is None and unit.has_zone2)
        ),
    ),
    MelCloudHomeSensorEntityDescription(
        key="tank_water_temperature",
        translation_key="tank_water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda unit, _: unit.tank_water_temperature,
    ),
    *_common_sensor_descriptions(ATWUnit),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home sensors."""
    coordinator = entry.runtime_data.coordinator
    energy_coordinator = entry.runtime_data.energy_coordinator

    async_setup_unit_entities(
        coordinator,
        async_add_entities,
        lambda units: chain(
            (
                ATASensor(coordinator, entity_description, unit)
                for entity_description in ATA_SENSORS
                for unit in units
                if entity_description.exists_fn(unit)
            ),
            (
                ATAEnergySensor(coordinator, energy_coordinator, unit)
                for unit in units
                if _has_energy_meter(unit)
            ),
        ),
        lambda units: chain(
            (
                ATWSensor(coordinator, entity_description, unit)
                for entity_description in ATW_SENSORS
                for unit in units
                if entity_description.exists_fn(unit)
            ),
            (
                ATWEnergySensor(coordinator, energy_coordinator, unit)
                for unit in units
                if _has_energy_meter(unit)
            ),
        ),
    )


class ATASensor(MelCloudHomeATAUnitEntity, SensorEntity):
    """Representation of a MELCloud Home ATA sensor."""

    entity_description: MelCloudHomeSensorEntityDescription[ATAUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeSensorEntityDescription[ATAUnit],
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
        return self.entity_description.value_fn(self.unit, self.coordinator)


class ATWSensor(MelCloudHomeATWUnitEntity, SensorEntity):
    """Representation of a MELCloud Home ATW sensor."""

    entity_description: MelCloudHomeSensorEntityDescription[ATWUnit]

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: MelCloudHomeSensorEntityDescription[ATWUnit],
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
        return self.entity_description.value_fn(self.unit, self.coordinator)


class ATAEnergySensor(MelCloudHomeATAUnitEntity, SensorEntity):
    """Representation of a MELCloud Home ATA energy sensor."""

    entity_description = ENERGY_CONSUMED_DESCRIPTION

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        energy_coordinator: MelCloudHomeEnergyCoordinator,
        unit: ATAUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self._energy_coordinator = energy_coordinator
        self._attr_unique_id = f"{unit.id}_{ENERGY_CONSUMED_DESCRIPTION.key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Also react to updates from the energy coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._energy_coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._energy_coordinator.last_update_success

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._energy_coordinator.data.get(self._unit_id)

    @property
    @override
    def last_reset(self) -> datetime:
        """Return start of month."""
        return utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class ATWEnergySensor(MelCloudHomeATWUnitEntity, SensorEntity):
    """Representation of a MELCloud Home ATW energy sensor."""

    entity_description = ENERGY_CONSUMED_DESCRIPTION

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        energy_coordinator: MelCloudHomeEnergyCoordinator,
        unit: ATWUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self._energy_coordinator = energy_coordinator
        self._attr_unique_id = f"{unit.id}_{ENERGY_CONSUMED_DESCRIPTION.key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Also react to updates from the energy coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._energy_coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._energy_coordinator.last_update_success

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._energy_coordinator.data.get(self._unit_id)

    @property
    @override
    def last_reset(self) -> datetime:
        """Return start of month."""
        return utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
