"""Base entity model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent
from music_assistant_models.player import Player

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient


class MusicAssistantEntity(Entity):
    """Base Entity from Music Assistant Player."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MediaPlayer entity."""
        self.mass = mass
        self.player_id = player_id
        provider = self.mass.get_provider(self.player.provider)
        if TYPE_CHECKING:
            assert provider is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player_id)},
            manufacturer=self.player.device_info.manufacturer or provider.name,
            model=self.player.device_info.model or self.player.name,
            name=self.player.display_name,
            configuration_url=f"{mass.server_url}/#/settings/editplayer/{player_id}",
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self.async_on_update()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update, EventType.PLAYER_UPDATED, self.player_id
            )
        )
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update,
                EventType.QUEUE_UPDATED,
            )
        )

    @property
    def player(self) -> Player:
        """Return the Mass Player attached to this HA entity."""
        return self.mass.players[self.player_id]

    @property
    def unique_id(self) -> str | None:
        """Return unique id for entity."""
        _base = self.player_id
        if hasattr(self, "entity_description"):
            return f"{_base}_{self.entity_description.key}"
        return _base

    @property
    def available(self) -> bool:
        """Return availability of entity."""
        return self.player.available and bool(self.mass.connection.connected)

    async def __on_mass_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        if event.event == EventType.QUEUE_UPDATED and event.object_id not in (
            self.player.active_source,
            self.player.active_group,
            self.player.player_id,
        ):
            return
        await self.async_on_update()
        self.async_write_ha_state()

    async def async_on_update(self) -> None:
        """Handle player updates."""
