"""Support for Mealie sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from aiomealie import Statistics

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import MealieConfigEntry, MealieStatisticsCoordinator
from .entity import MealieEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MealieStatisticsSensorEntityDescription(SensorEntityDescription):
    """Describes Mealie Statistics sensor entity."""

    value_fn: Callable[[Statistics], StateType]


SENSOR_TYPES: tuple[MealieStatisticsSensorEntityDescription, ...] = (
    MealieStatisticsSensorEntityDescription(
        key="recipes",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda statistics: statistics.total_recipes,
    ),
    MealieStatisticsSensorEntityDescription(
        key="users",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda statistics: statistics.total_users,
    ),
    MealieStatisticsSensorEntityDescription(
        key="categories",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda statistics: statistics.total_categories,
    ),
    MealieStatisticsSensorEntityDescription(
        key="tags",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda statistics: statistics.total_tags,
    ),
    MealieStatisticsSensorEntityDescription(
        key="tools",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda statistics: statistics.total_tools,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MealieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mealie sensors based on a config entry."""
    coordinator = entry.runtime_data.statistics_coordinator

    async_add_entities(
        MealieStatisticSensors(coordinator, description) for description in SENSOR_TYPES
    )


class MealieStatisticSensors(MealieEntity, SensorEntity):
    """Defines a Mealie sensor."""

    entity_description: MealieStatisticsSensorEntityDescription
    coordinator: MealieStatisticsCoordinator

    def __init__(
        self,
        coordinator: MealieStatisticsCoordinator,
        description: MealieStatisticsSensorEntityDescription,
    ) -> None:
        """Initialize Mealie sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
