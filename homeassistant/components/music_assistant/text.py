"""Music Assistant text platform."""

from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry, PlatformHandlers
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
    # player_id -> keys of the player options that got an entity
    added_option_keys_by_player: dict[str, set[str]] = {}

    def add_player_options(player_id: str) -> None:
        """Add entities for the player options that do not have one yet."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigText] = []
        added_option_keys = added_option_keys_by_player.setdefault(player_id, set())
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.STRING
                and not player_option.options  # these we map to select
            ):
                # we ignore entities with unknown translation keys.
                if (
                    player_option.translation_key not in PLAYER_OPTIONS_TEXT
                    or player_option.key in added_option_keys
                ):
                    continue
                added_option_keys.add(player_option.key)

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

    def remove_player(player_id: str) -> None:
        """Forget the option keys of a removed player."""
        added_option_keys_by_player.pop(player_id, None)

    entry.runtime_data.platform_handlers.setdefault(
        Platform.TEXT,
        PlatformHandlers(
            add_player=add_player_options,
            remove_player=remove_player,
            update_player_options=add_player_options,
        ),
    )


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
    @override
    async def async_set_value(self, value: str) -> None:
        """Set text value."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, value)

    @override
    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_native_value = (
            player_option.value if isinstance(player_option.value, str) else None
        )
