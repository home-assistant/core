"""Music Assistant sensor platform."""

from typing import override

from music_assistant_models.enums import EventType, SleepTimerMode
from music_assistant_models.event import MassEvent
from music_assistant_models.player import Player

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from . import MusicAssistantConfigEntry, PlatformHandlers
from .entity import MusicAssistantEntity

ATTR_MODE = "mode"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant sensors from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        async_add_entities([MusicAssistantSleepTimerSensor(mass, player_id)])

    entry.runtime_data.platform_handlers.setdefault(
        Platform.SENSOR, PlatformHandlers(add_player=add_player)
    )


class MusicAssistantSleepTimerSensor(MusicAssistantEntity, SensorEntity):
    """When the sleep timer of a player stops playback, and in which mode."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "sleep_timer"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks, also for the player it plays along with."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.mass.subscribe(
                self._on_sleep_timer_updated, EventType.PLAYER_SLEEP_TIMER_UPDATED
            )
        )

    async def _on_sleep_timer_updated(self, event: MassEvent) -> None:
        # the server updates the player before it signals its sleep timer
        if event.object_id in (self.player_id, self.player.active_source):
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
        player = self._timer_player
        expires_at = player.sleep_timer_expires_at
        self._attr_native_value = (
            utc_from_timestamp(expires_at) if expires_at is not None else None
        )
        mode: str | None = player.sleep_timer_mode
        if mode is None:
            # servers before schema 105 only report when a duration timer ends
            mode = SleepTimerMode.DURATION if expires_at is not None else "off"
        elif mode is SleepTimerMode.UNKNOWN:
            # a mode of a newer server
            mode = None
        self._attr_extra_state_attributes = {ATTR_MODE: mode}
