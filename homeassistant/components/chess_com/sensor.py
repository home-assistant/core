"""Sensor platform for Chess.com integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from chess_com_api import PlayerStats

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ChessConfigEntry
from .coordinator import ChessCoordinator, ChessData
from .entity import ChessEntity


@dataclass(kw_only=True, frozen=True)
class ChessEntityDescription(SensorEntityDescription):
    """Sensor description for Chess.com player."""

    value_fn: Callable[[ChessData], float]


@dataclass(kw_only=True, frozen=True)
class ChessModeEntityDescription(SensorEntityDescription):
    """Sensor description for a Chess.com game mode."""

    value_fn: Callable[[dict[str, Any]], float]


PLAYER_SENSORS: tuple[ChessEntityDescription, ...] = (
    ChessEntityDescription(
        key="followers",
        translation_key="followers",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.player.followers,
        entity_registry_enabled_default=False,
    ),
)

GAME_MODE_SENSORS: tuple[ChessModeEntityDescription, ...] = (
    ChessModeEntityDescription(
        key="rating",
        translation_key="rating",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda mode: mode["last"]["rating"],
    ),
    ChessModeEntityDescription(
        key="won",
        translation_key="won",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda mode: mode["record"]["win"],
    ),
    ChessModeEntityDescription(
        key="lost",
        translation_key="lost",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda mode: mode["record"]["loss"],
    ),
    ChessModeEntityDescription(
        key="draw",
        translation_key="draw",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda mode: mode["record"]["draw"],
    ),
)

GAME_MODES: dict[str, Callable[[PlayerStats], dict[str, Any] | None]] = {
    "chess_daily": lambda stats: stats.chess_daily,
    "chess_rapid": lambda stats: stats.chess_rapid,
    "chess_bullet": lambda stats: stats.chess_bullet,
    "chess_blitz": lambda stats: stats.chess_blitz,
    "chess960_daily": lambda stats: stats.chess960_daily,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        ChessPlayerSensor(coordinator, description) for description in PLAYER_SENSORS
    ]

    for game_mode, stats_fn in GAME_MODES.items():
        if stats_fn(coordinator.data.stats) is not None:
            entities.extend(
                ChessGameModeSensor(coordinator, description, game_mode, stats_fn)
                for description in GAME_MODE_SENSORS
            )

    async_add_entities(entities)


class ChessPlayerSensor(ChessEntity, SensorEntity):
    """Chess.com player sensor."""

    entity_description: ChessEntityDescription

    def __init__(
        self,
        coordinator: ChessCoordinator,
        description: ChessEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}.{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class ChessGameModeSensor(ChessEntity, SensorEntity):
    """Chess.com game mode sensor."""

    entity_description: ChessModeEntityDescription

    def __init__(
        self,
        coordinator: ChessCoordinator,
        description: ChessModeEntityDescription,
        game_mode: str,
        stats_fn: Callable[[PlayerStats], dict[str, Any] | None],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._stats_fn = stats_fn
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}.{game_mode}.{description.key}"
        )
        self._attr_translation_key = f"{game_mode}_{description.translation_key}"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        mode_data = self._stats_fn(self.coordinator.data.stats)
        if TYPE_CHECKING:
            assert mode_data is not None
        return self.entity_description.value_fn(mode_data)
