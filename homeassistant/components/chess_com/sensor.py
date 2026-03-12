"""Sensor platform for Chess.com integration."""

from collections.abc import Callable
from dataclasses import dataclass

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


SENSORS: tuple[ChessEntityDescription, ...] = (
    ChessEntityDescription(
        key="followers",
        translation_key="followers",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.player.followers,
        entity_registry_enabled_default=False,
    ),
    ChessEntityDescription(
        key="chess_daily_rating",
        translation_key="chess_daily_rating",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.stats.chess_daily["last"]["rating"],
    ),
    ChessEntityDescription(
        key="total_daily_won",
        translation_key="total_daily_won",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.stats.chess_daily["record"]["win"],
    ),
    ChessEntityDescription(
        key="total_daily_lost",
        translation_key="total_daily_lost",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.stats.chess_daily["record"]["loss"],
    ),
    ChessEntityDescription(
        key="total_daily_draw",
        translation_key="total_daily_draw",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state: state.stats.chess_daily["record"]["draw"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""
    coordinator = entry.runtime_data

    async_add_entities(
        ChessPlayerSensor(coordinator, description) for description in SENSORS
    )


class ChessPlayerSensor(ChessEntity, SensorEntity):
    """Chess.com sensor."""

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
