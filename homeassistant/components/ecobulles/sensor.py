"""Sensor platform for Ecobulles."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EcobullesConfigEntry
from .const import DOMAIN
from .coordinator import EcobullesCoordinator, EcobullesData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EcobullesSensorDescription(SensorEntityDescription):
    """Describe an Ecobulles sensor."""

    value_fn: Callable[[EcobullesData], StateType]


SENSORS: tuple[EcobullesSensorDescription, ...] = (
    EcobullesSensorDescription(
        key="water_usage",
        translation_key="water_usage",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.water_liters,
    ),
    EcobullesSensorDescription(
        key="co2_injection_time",
        translation_key="co2_injection_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.co2_injection_time_seconds,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcobullesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ecobulles sensors from a config entry."""
    assert entry.unique_id is not None
    async_add_entities(
        EcobullesSensor(entry.runtime_data, entry.unique_id, description)
        for description in SENSORS
    )


class EcobullesSensor(CoordinatorEntity[EcobullesCoordinator], SensorEntity):
    """Ecobulles sensor backed by an entity description."""

    _attr_has_entity_name = True
    entity_description: EcobullesSensorDescription

    def __init__(
        self,
        coordinator: EcobullesCoordinator,
        eco_ref: str,
        description: EcobullesSensorDescription,
    ) -> None:
        """Initialize an Ecobulles sensor."""
        super().__init__(coordinator)
        self.eco_ref = eco_ref
        self.entity_description = description
        self._attr_unique_id = f"{eco_ref}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry metadata."""
        return DeviceInfo(identifiers={(DOMAIN, self.eco_ref)})

    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
