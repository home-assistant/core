"""Sensor platform for Lichess integration."""

from collections.abc import Callable
from dataclasses import dataclass

from aiolichess.models import LichessStatistics

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LichessConfigEntry
from .coordinator import LichessCoordinator
from .entity import LichessEntity


@dataclass(kw_only=True, frozen=True)
class LichessEntityDescription(SensorEntityDescription):
    """Sensor description for Lichess player."""

    value_fn: Callable[[LichessStatistics], int | None]


SENSORS: tuple[LichessEntityDescription, ...] = (
    LichessEntityDescription(
        key="bullet_rating",
        translation_key="bullet_rating",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.bullet_rating,
    ),
    LichessEntityDescription(
        key="bullet_games",
        translation_key="bullet_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.bullet_games,
    ),
    LichessEntityDescription(
        key="blitz_rating",
        translation_key="blitz_rating",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.blitz_rating,
    ),
    LichessEntityDescription(
        key="blitz_games",
        translation_key="blitz_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.blitz_games,
    ),
    LichessEntityDescription(
        key="rapid_rating",
        translation_key="rapid_rating",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.rapid_rating,
    ),
    LichessEntityDescription(
        key="rapid_games",
        translation_key="rapid_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.rapid_games,
    ),
    LichessEntityDescription(
        key="classical_rating",
        translation_key="classical_rating",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.classical_rating,
    ),
    LichessEntityDescription(
        key="classical_games",
        translation_key="classical_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.classical_games,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LichessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""
    coordinator = entry.runtime_data

    async_add_entities(
        LichessPlayerSensor(coordinator, description) for description in SENSORS
    )


class LichessPlayerSensor(LichessEntity, SensorEntity):
    """Lichess sensor."""

    entity_description: LichessEntityDescription

    def __init__(
        self,
        coordinator: LichessCoordinator,
        description: LichessEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}.{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
