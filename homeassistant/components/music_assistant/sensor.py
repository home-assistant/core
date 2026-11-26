"""Music Assistant sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import EventType, SleepTimerMode
from music_assistant_models.event import MassEvent
from music_assistant_models.player import Player

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from . import MusicAssistantConfigEntry, PlatformHandlers
from .entity import MusicAssistantEntity


@dataclass(frozen=True, kw_only=True)
class MusicAssistantSensorDescription(SensorEntityDescription):
    """Describes a sensor for a state of a player."""

    value_fn: Callable[[Player], datetime | str | None]


def _sleep_timer_mode(player: Player) -> str | None:
    if (mode := player.sleep_timer_mode) is None:
        # servers before schema 105 only report when a duration timer ends
        return (
            SleepTimerMode.DURATION
            if player.sleep_timer_expires_at is not None
            else "off"
        )
    # a mode of a newer server
    return None if mode is SleepTimerMode.UNKNOWN else mode


SENSORS: Final = (
    MusicAssistantSensorDescription(
        key="sleep_timer_end",
        translation_key="sleep_timer_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda player: (
            utc_from_timestamp(player.sleep_timer_expires_at)
            if player.sleep_timer_expires_at is not None
            else None
        ),
    ),
    MusicAssistantSensorDescription(
        key="sleep_timer_mode",
        translation_key="sleep_timer_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            SleepTimerMode.DURATION,
            SleepTimerMode.END_OF_ITEM,
            SleepTimerMode.END_OF_CHAPTER,
        ],
        entity_registry_enabled_default=False,
        value_fn=_sleep_timer_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant sensors from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        async_add_entities(
            MusicAssistantSensor(mass, player_id, description)
            for description in SENSORS
        )

    entry.runtime_data.platform_handlers.setdefault(
        Platform.SENSOR, PlatformHandlers(add_player=add_player)
    )


class MusicAssistantSensor(MusicAssistantEntity, SensorEntity):
    """Sensor for a state of a player."""

    entity_description: MusicAssistantSensorDescription

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        entity_description: MusicAssistantSensorDescription,
    ) -> None:
        """Initialize MusicAssistantSensor."""
        super().__init__(mass, player_id)
        self.entity_description = entity_description

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks, also for the player it plays along with."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.mass.subscribe(self._on_player_updated, EventType.PLAYER_UPDATED)
        )

    async def _on_player_updated(self, event: MassEvent) -> None:
        # updates of the player itself already reach the base entity
        if event.object_id != self.player_id and (
            event.object_id == self.player.active_source
        ):
            await self.async_on_update()
            self.async_write_ha_state()

    @property
    def _timer_player(self) -> Player:
        # a player playing along with another one shares that player's sleep timer
        if (source := self.player.active_source) and (
            owner := self.mass.players.get(source)
        ):
            return owner
        return self.player

    @override
    async def async_on_update(self) -> None:
        """Handle player updates."""
        self._attr_native_value = self.entity_description.value_fn(self._timer_player)
