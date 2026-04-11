"""Music Assistant text platform."""

from __future__ import annotations

from typing import Final

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_OPTIONS_TEXT: Final[dict[str, bool]] = {
    # translation_key: enabled_by_default
    "network_name": True
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant text Entities (Player Options) from Config Entry."""
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
                # we ignore entities with unknown translation keys.
                if player_option.translation_key not in PLAYER_OPTIONS_TEXT:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigText(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=TextEntityDescription(
                            key=player_option.key,
                            translation_key=player_option.translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_TEXT[
                                player_option.translation_key
                            ],
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.TEXT, add_player)


class MusicAssistantPlayerConfigText(MusicAssistantPlayerOptionEntity, TextEntity):
    """Representation of a text entity to control player provider dependent settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        player_option: PlayerOption,
        entity_description: TextEntityDescription,
    ) -> None:
        """Initialize MusicAssistantPlayerConfigtext."""
        super().__init__(mass, player_id, player_option)

        self.entity_description = entity_description

    @catch_musicassistant_error
    async def async_set_value(self, value: str) -> None:
        """Set text value."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, value)

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_native_value = (
            player_option.value if isinstance(player_option.value, str) else None
        )
