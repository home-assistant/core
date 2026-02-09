"""Music Assistant Text platform."""

from __future__ import annotations

from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.text import TextEntity, TextEntityDescription
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
        entities: list[MusicAssistantPlayerConfigText] = []
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.STRING
                and not player_option.options  # these we map to select
            ):
                entities.extend(
                    [
                        MusicAssistantPlayerConfigText(
                            mass, player_id, player_option=player_option
                        )
                    ]
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.TEXT, add_player)


class MusicAssistantPlayerConfigText(MusicAssistantPlayerOptionEntity, TextEntity):
    """Representation of a Number entity to control player provider dependent settings."""

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        super().on_player_option_update(player_option)

        self.entity_description = TextEntityDescription(
            name=player_option.name,
            key=player_option.key,
            translation_key=player_option.translation_key or player_option.name,
        )

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return str(self.mass_value)

    @catch_musicassistant_error
    async def async_set_value(self, value: str) -> None:
        """Set text value."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, value)
