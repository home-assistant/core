"""Binary sensor entities for SmartyPlants."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pysmartyplants import Sensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmartyPlantsConfigEntry, SmartyPlantsCoordinator
from .entity import SmartyPlantsEntity, is_stale

# Read-only and coordinator-driven, so updates need not be serialized.
PARALLEL_UPDATES = 0


def _needs_attention(sensor: Sensor) -> bool | None:
    """Return whether the backend has flagged the plant."""
    if sensor.health is None or sensor.health.is_healthy is None:
        return None
    return not sensor.health.is_healthy


@dataclass(frozen=True, kw_only=True)
class SmartyPlantsBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one SmartyPlants binary sensor."""

    is_on_fn: Callable[[Sensor], bool | None]
    requires_online: bool = True


BINARY_SENSOR_TYPES: tuple[SmartyPlantsBinarySensorDescription, ...] = (
    SmartyPlantsBinarySensorDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        # Readings that stopped arriving hours ago are not a live connection,
        # so staleness reads as disconnected here.
        is_on_fn=lambda sensor: sensor.is_online and not is_stale(sensor),
    ),
    SmartyPlantsBinarySensorDescription(
        key="stale",
        translation_key="stale",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        is_on_fn=is_stale,
    ),
    SmartyPlantsBinarySensorDescription(
        key="needs_attention",
        translation_key="needs_attention",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_needs_attention,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyPlantsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors for every physical sensor."""
    coordinator = entry.runtime_data

    async_add_entities(
        SmartyPlantsBinarySensor(coordinator, sensor_id, description)
        for sensor_id in coordinator.data
        for description in BINARY_SENSOR_TYPES
    )


class SmartyPlantsBinarySensor(SmartyPlantsEntity, BinarySensorEntity):
    """Connectivity, staleness and health state for a SmartyPlants sensor."""

    entity_description: SmartyPlantsBinarySensorDescription

    def __init__(
        self,
        coordinator: SmartyPlantsCoordinator,
        sensor_id: str,
        description: SmartyPlantsBinarySensorDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator, sensor_id)
        self.entity_description = description
        self._attr_unique_id = f"{sensor_id}_{description.key}"
        self._requires_online = description.requires_online

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the current state."""
        return self.entity_description.is_on_fn(self.sensor)
