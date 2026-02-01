"""Music Assistant Switch platform."""

from __future__ import annotations

from typing import Any

from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant MediaPlayer(s) from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigSwitch] = []
        for player_option in player.player_options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.BOOLEAN
            ):
                entities.extend(
                    [
                        # Add button entity to favorite the currently playing item on the player
                        MusicAssistantPlayerConfigSwitch(
                            mass, player_id, player_option=player_option
                        )
                    ]
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SWITCH, add_player)


class MusicAssistantPlayerConfigSwitch(MusicAssistantPlayerOptionEntity, SwitchEntity):
    """Representation of a Switch entity to control player provider dependent settings."""

    @catch_musicassistant_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle turn on command."""
        await self.mass.players.set_player_option(self.player_id, self.option_id, True)

    @catch_musicassistant_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle turn on command."""
        await self.mass.players.set_player_option(self.player_id, self.option_id, False)

    @property
    def is_on(self) -> bool:
        """Return the current status."""
        assert isinstance(self.value, bool)
        return self.value

    async def async_on_update(self) -> None:
        """Handle player updates."""
        if player := self.mass.players.get(self.player_id):
            for option in player.player_options:
                if option.id == self.option_id:
                    self.value = option.value
                    self.update_description(option)
                    break

    def update_description(self, option: PlayerOption) -> None:
        """Update switch's description."""
        self.entity_description = SwitchEntityDescription(
            name=option.name,
            key=option.translation_key or "",
            translation_key=option.translation_key or "",
        )
