"""Sensor platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from yoto_api import CardInsertionState, DayMode, YotoPlayer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoPlayerEntity

PARALLEL_UPDATES = 0


def _enum_state(value: CardInsertionState | None) -> str | None:
    """Return an enum member as a lowercase string, or None if unset."""
    return value.name.lower() if value is not None else None


def _day_mode_state(value: DayMode | None) -> str | None:
    """Return day/night, treating the firmware's UNKNOWN as unset."""
    if value is None or value is DayMode.UNKNOWN:
        return None
    return value.name.lower()


@dataclass(frozen=True, kw_only=True)
class YotoSensorEntityDescription(SensorEntityDescription):
    """Describes a Yoto sensor entity."""

    value_fn: Callable[[YotoPlayer], StateType]


SENSORS: tuple[YotoSensorEntityDescription, ...] = (
    YotoSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda player: player.status.battery_level_percentage,
    ),
    YotoSensorEntityDescription(
        key="card_insertion_state",
        translation_key="card_insertion_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.name.lower() for state in CardInsertionState],
        value_fn=lambda player: _enum_state(player.status.card_insertion_state),
    ),
    YotoSensorEntityDescription(
        key="day_mode",
        translation_key="day_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["day", "night"],
        value_fn=lambda player: _day_mode_state(player.status.day_mode),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto sensor platform."""
    coordinator = entry.runtime_data
    known_players: set[str] = set()

    @callback
    def _add_players() -> None:
        current = set(coordinator.data)
        new_players = current - known_players
        known_players.clear()
        known_players.update(current)
        if new_players:
            async_add_entities(
                YotoSensor(coordinator, coordinator.data[player_id], description)
                for player_id in new_players
                for description in SENSORS
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_players))
    _add_players()


class YotoSensor(YotoPlayerEntity, SensorEntity):
    """Representation of a Yoto player sensor."""

    entity_description: YotoSensorEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.player)
