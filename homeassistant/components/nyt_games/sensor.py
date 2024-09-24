"""Support for NYT Games sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from nyt_games import Wordle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import NYTGamesConfigEntry
from .coordinator import NYTGamesCoordinator
from .entity import NYTGamesEntity


@dataclass(frozen=True, kw_only=True)
class NYTGamesWordleSensorEntityDescription(SensorEntityDescription):
    """Describes a NYT Games Wordle sensor entity."""

    value_fn: Callable[[Wordle], StateType]


SENSOR_TYPES: tuple[NYTGamesWordleSensorEntityDescription, ...] = (
    NYTGamesWordleSensorEntityDescription(
        key="wordles_played",
        translation_key="wordles_played",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="games",
        value_fn=lambda wordle: wordle.games_played,
    ),
    NYTGamesWordleSensorEntityDescription(
        key="wordles_won",
        translation_key="wordles_won",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="games",
        value_fn=lambda wordle: wordle.games_won,
    ),
    NYTGamesWordleSensorEntityDescription(
        key="wordles_streak",
        translation_key="wordles_streak",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda wordle: wordle.current_streak,
    ),
    NYTGamesWordleSensorEntityDescription(
        key="wordles_max_streak",
        translation_key="wordles_max_streak",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda wordle: wordle.max_streak,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NYTGamesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NYT Games sensor entities based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        NYTGamesSensor(coordinator, description) for description in SENSOR_TYPES
    )


class NYTGamesSensor(NYTGamesEntity, SensorEntity):
    """Defines a NYT Games sensor."""

    entity_description: NYTGamesWordleSensorEntityDescription

    def __init__(
        self,
        coordinator: NYTGamesCoordinator,
        description: NYTGamesWordleSensorEntityDescription,
    ) -> None:
        """Initialize NYT Games sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
