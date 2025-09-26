"""Support for NYT Games sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from nyt_games import Connections, SpellingBee, Wordle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NYTGamesConfigEntry, NYTGamesCoordinator
from .entity import ConnectionsEntity, SpellingBeeEntity, WordleEntity


@dataclass(frozen=True, kw_only=True)
class NYTGamesWordleSensorEntityDescription(SensorEntityDescription):
    """Describes a NYT Games Wordle sensor entity."""

    value_fn: Callable[[Wordle], StateType]


WORDLE_SENSORS: tuple[NYTGamesWordleSensorEntityDescription, ...] = (
    NYTGamesWordleSensorEntityDescription(
        key="wordles_played",
        translation_key="wordles_played",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="games",
        value_fn=lambda wordle: wordle.games_played,
    ),
    NYTGamesWordleSensorEntityDescription(
        key="wordles_won",
        translation_key="won",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="games",
        value_fn=lambda wordle: wordle.games_won,
    ),
    NYTGamesWordleSensorEntityDescription(
        key="wordles_streak",
        translation_key="streak",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda wordle: wordle.current_streak,
    ),
    NYTGamesWordleSensorEntityDescription(
        key="wordles_max_streak",
        translation_key="max_streak",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda wordle: wordle.max_streak,
    ),
)


@dataclass(frozen=True, kw_only=True)
class NYTGamesSpellingBeeSensorEntityDescription(SensorEntityDescription):
    """Describes a NYT Games Spelling Bee sensor entity."""

    value_fn: Callable[[SpellingBee], StateType]


SPELLING_BEE_SENSORS: tuple[NYTGamesSpellingBeeSensorEntityDescription, ...] = (
    NYTGamesSpellingBeeSensorEntityDescription(
        key="spelling_bees_played",
        translation_key="spelling_bees_played",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="games",
        value_fn=lambda spelling_bee: spelling_bee.puzzles_started,
    ),
    NYTGamesSpellingBeeSensorEntityDescription(
        key="spelling_bees_total_words",
        translation_key="total_words",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="words",
        entity_registry_enabled_default=False,
        value_fn=lambda spelling_bee: spelling_bee.total_words,
    ),
    NYTGamesSpellingBeeSensorEntityDescription(
        key="spelling_bees_total_pangrams",
        translation_key="total_pangrams",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="pangrams",
        entity_registry_enabled_default=False,
        value_fn=lambda spelling_bee: spelling_bee.total_pangrams,
    ),
)


@dataclass(frozen=True, kw_only=True)
class NYTGamesConnectionsSensorEntityDescription(SensorEntityDescription):
    """Describes a NYT Games Connections sensor entity."""

    value_fn: Callable[[Connections], StateType | date]


CONNECTIONS_SENSORS: tuple[NYTGamesConnectionsSensorEntityDescription, ...] = (
    NYTGamesConnectionsSensorEntityDescription(
        key="connections_played",
        translation_key="connections_played",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="games",
        value_fn=lambda connections: connections.puzzles_completed,
    ),
    NYTGamesConnectionsSensorEntityDescription(
        key="connections_won",
        translation_key="won",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="games",
        value_fn=lambda connections: connections.puzzles_won,
    ),
    NYTGamesConnectionsSensorEntityDescription(
        key="connections_last_played",
        translation_key="last_played",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda connections: connections.last_completed,
    ),
    NYTGamesConnectionsSensorEntityDescription(
        key="connections_streak",
        translation_key="streak",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda connections: connections.current_streak,
    ),
    NYTGamesConnectionsSensorEntityDescription(
        key="connections_max_streak",
        translation_key="max_streak",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda connections: connections.max_streak,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NYTGamesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NYT Games sensor entities based on a config entry."""

    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        NYTGamesWordleSensor(coordinator, description) for description in WORDLE_SENSORS
    ]
    if coordinator.data.spelling_bee is not None:
        entities.extend(
            NYTGamesSpellingBeeSensor(coordinator, description)
            for description in SPELLING_BEE_SENSORS
        )
    if coordinator.data.connections is not None:
        entities.extend(
            NYTGamesConnectionsSensor(coordinator, description)
            for description in CONNECTIONS_SENSORS
        )

    async_add_entities(entities)


class NYTGamesWordleSensor(WordleEntity, SensorEntity):
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
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}-wordle-{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.wordle)


class NYTGamesSpellingBeeSensor(SpellingBeeEntity, SensorEntity):
    """Defines a NYT Games sensor."""

    entity_description: NYTGamesSpellingBeeSensorEntityDescription

    def __init__(
        self,
        coordinator: NYTGamesCoordinator,
        description: NYTGamesSpellingBeeSensorEntityDescription,
    ) -> None:
        """Initialize NYT Games sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}-spelling_bee-{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        assert self.coordinator.data.spelling_bee is not None
        return self.entity_description.value_fn(self.coordinator.data.spelling_bee)


class NYTGamesConnectionsSensor(ConnectionsEntity, SensorEntity):
    """Defines a NYT Games sensor."""

    entity_description: NYTGamesConnectionsSensorEntityDescription

    def __init__(
        self,
        coordinator: NYTGamesCoordinator,
        description: NYTGamesConnectionsSensorEntityDescription,
    ) -> None:
        """Initialize NYT Games sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}-connections-{description.key}"
        )

    @property
    def native_value(self) -> StateType | date:
        """Return the state of the sensor."""
        assert self.coordinator.data.connections is not None
        return self.entity_description.value_fn(self.coordinator.data.connections)
