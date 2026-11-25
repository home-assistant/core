"""Music Assistant select platform."""

from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry, PlatformHandlers
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_OPTIONS_SELECT: Final[dict[str, bool]] = {
    # translation_key: enabled_by_default
    "dimmer": False,
    "equalizer_mode": False,
    "link_audio_delay": True,
    "link_audio_quality": False,
    "link_control": False,
    "sleep": False,
    "surround_decoder_type": False,
    "tone_control_mode": True,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Select Entities (Player Options) from Config Entry."""
    mass = entry.runtime_data.mass
    # player_id -> keys of the player options that got an entity
    added_option_keys_by_player: dict[str, set[str]] = {}

    def add_player_options(player_id: str) -> None:
        """Add entities for the player options that do not have one yet."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigSelect] = []
        added_option_keys = added_option_keys_by_player.setdefault(player_id, set())
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type
                != PlayerOptionType.BOOLEAN  # these always go to switch
                and player_option.options
            ):
                # We ignore entities with unknown
                # translation key for the base name.
                # However, we accept a non-available
                # translation_key in strings.json for the
                # entity's state, as these are oftentimes
                # dynamically created, dependent on a
                # specific player and might not be known to
                # the provider developer. In that case, the
                # frontend falls back to showing the state's
                # bare translation key.
                if (
                    player_option.translation_key not in PLAYER_OPTIONS_SELECT
                    or player_option.key in added_option_keys
                ):
                    continue
                added_option_keys.add(player_option.key)

                entities.append(
                    MusicAssistantPlayerConfigSelect(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=SelectEntityDescription(
                            key=player_option.key,
                            translation_key=player_option.translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_SELECT[
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
        Platform.SELECT,
        PlatformHandlers(
            add_player=add_player_options,
            remove_player=remove_player,
            update_player_options=add_player_options,
        ),
    )


class MusicAssistantPlayerConfigSelect(MusicAssistantPlayerOptionEntity, SelectEntity):
    """Representation of a select entity to control player settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        player_option: PlayerOption,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize MusicAssistantPlayerConfigSelect."""
        # this was verified already in the entry callback
        assert player_option.options is not None
        # we have to define the dicts before initializing the parent, as this
        # then calls self.on_player_option_update
        self._option_translation_key_to_key_mapping = {
            option.translation_key: option.key for option in player_option.options
        }
        self._option_key_to_translation_key_mapping = {
            option.key: option.translation_key for option in player_option.options
        }

        super().__init__(mass, player_id, player_option)

        self.entity_description = entity_description

        self._attr_options = list(self._option_translation_key_to_key_mapping.keys())

    @catch_musicassistant_error
    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.mass.players.set_option(
            self.player_id,
            self.mass_option_key,
            self._option_translation_key_to_key_mapping[option],
        )

    @override
    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_current_option = (
            self._option_key_to_translation_key_mapping.get(player_option.value)
            if isinstance(player_option.value, str)
            else None
        )
