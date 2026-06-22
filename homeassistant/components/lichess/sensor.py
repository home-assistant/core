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
    LichessEntityDescription(
        key="ultra_bullet_rating",
        translation_key="ultra_bullet_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.ultra_bullet_rating,
    ),
    LichessEntityDescription(
        key="ultra_bullet_games",
        translation_key="ultra_bullet_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.ultra_bullet_games,
    ),
    LichessEntityDescription(
        key="correspondence_rating",
        translation_key="correspondence_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.correspondence_rating,
    ),
    LichessEntityDescription(
        key="correspondence_games",
        translation_key="correspondence_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.correspondence_games,
    ),
    LichessEntityDescription(
        key="chess960_rating",
        translation_key="chess960_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.chess960_rating,
    ),
    LichessEntityDescription(
        key="chess960_games",
        translation_key="chess960_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.chess960_games,
    ),
    LichessEntityDescription(
        key="crazyhouse_rating",
        translation_key="crazyhouse_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.crazyhouse_rating,
    ),
    LichessEntityDescription(
        key="crazyhouse_games",
        translation_key="crazyhouse_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.crazyhouse_games,
    ),
    LichessEntityDescription(
        key="antichess_rating",
        translation_key="antichess_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.antichess_rating,
    ),
    LichessEntityDescription(
        key="antichess_games",
        translation_key="antichess_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.antichess_games,
    ),
    LichessEntityDescription(
        key="atomic_rating",
        translation_key="atomic_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.atomic_rating,
    ),
    LichessEntityDescription(
        key="atomic_games",
        translation_key="atomic_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.atomic_games,
    ),
    LichessEntityDescription(
        key="horde_rating",
        translation_key="horde_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.horde_rating,
    ),
    LichessEntityDescription(
        key="horde_games",
        translation_key="horde_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.horde_games,
    ),
    LichessEntityDescription(
        key="king_of_the_hill_rating",
        translation_key="king_of_the_hill_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.king_of_the_hill_rating,
    ),
    LichessEntityDescription(
        key="king_of_the_hill_games",
        translation_key="king_of_the_hill_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.king_of_the_hill_games,
    ),
    LichessEntityDescription(
        key="racing_kings_rating",
        translation_key="racing_kings_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.racing_kings_rating,
    ),
    LichessEntityDescription(
        key="racing_kings_games",
        translation_key="racing_kings_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.racing_kings_games,
    ),
    LichessEntityDescription(
        key="three_check_rating",
        translation_key="three_check_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.three_check_rating,
    ),
    LichessEntityDescription(
        key="three_check_games",
        translation_key="three_check_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.three_check_games,
    ),
    LichessEntityDescription(
        key="puzzle_rating",
        translation_key="puzzle_rating",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.puzzle_rating,
    ),
    LichessEntityDescription(
        key="puzzle_games",
        translation_key="puzzle_games",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.puzzle_games,
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
