"""Music Assistant Time platform."""

from datetime import datetime, time, timedelta
from typing import override

from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import MusicAssistantConfigEntry
from .entity import MusicAssistantEntity
from .helpers import catch_musicassistant_error


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Time entities from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        async_add_entities([MusicAssistantPlayerSleepTimerTime(mass, player_id)])

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.TIME, add_player)


class MusicAssistantPlayerSleepTimerTime(MusicAssistantEntity, TimeEntity):
    """Representation of a Music Assistant sleep timer time entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "sleep_timer"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_sleep_timer_update,
                EventType.PLAYER_SLEEP_TIMER_UPDATED,
                self.player_id,
            )
        )

    async def __on_sleep_timer_update(self, event: MassEvent) -> None:
        """Handle sleep timer updates."""
        await self.async_on_update()
        self.async_write_ha_state()

    @override
    async def async_on_update(self) -> None:
        """Handle player updates."""
        expiry = await self.mass.players.get_sleep_timer(self.player_id)
        self._attr_native_value = (
            dt_util.as_local(expiry).time() if expiry is not None else None
        )

    @catch_musicassistant_error
    @override
    async def async_set_value(self, value: time) -> None:
        """Set the sleep timer expiry time."""
        now = dt_util.now()
        expiry = datetime.combine(now.date(), value, tzinfo=now.tzinfo)
        if expiry <= now:
            expiry += timedelta(days=1)
        await self.mass.players.set_sleep_timer(
            self.player_id, int((expiry - now).total_seconds())
        )
