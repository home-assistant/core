"""Music Assistant Button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .entity import MusicAssistantEntity
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
        async_add_entities(
            [
                # Add button entity to favorite the currently playing item on the player
                MusicAssistantFavoriteButton(mass, player_id)
            ]
        )

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.BUTTON, add_player)


class MusicAssistantFavoriteButton(MusicAssistantEntity, ButtonEntity):
    """Representation of a Button entity to favorite the currently playing item on a player."""

    entity_description = ButtonEntityDescription(
        key="favorite_now_playing",
        translation_key="favorite_now_playing",
    )

    @catch_musicassistant_error
    async def async_press(self) -> None:
        """Handle the button press command."""
        await self.mass.players.add_currently_playing_to_favorites(self.player_id)
