"""Support for NYT Games sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from nyt_games import Wordle

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
