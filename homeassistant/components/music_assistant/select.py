"""Music Assistant select platform."""

from __future__ import annotations

from typing import Final

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
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

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigSelect] = []
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type
                != PlayerOptionType.BOOLEAN  # these always go to switch
                and player_option.options
            ):
                # We ignore entities with unknown translation key for the base name.
                # However, we accept a non-available translation_key in strings.json for the entity's state,
                # as these are oftentimes dynamically created, dependent on a specific player and might not be known to the provider
                # developer. In that case, the frontend falls back to showing the state's bare translation key.
                if player_option.translation_key not in PLAYER_OPTIONS_SELECT:
                    continue

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

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SELECT, add_player)


class MusicAssistantPlayerConfigSelect(MusicAssistantPlayerOptionEntity, SelectEntity):
    """Representation of a select entity to control player provider dependent settings."""

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
        self._option_translation_key_to_key_mapping = {
            option.translation_key: option.key for option in player_option.options
        }
        self._option_key_to_translation_key_mapping = {
            option.key: option.translation_key for option in player_option.options
        }
        self._attr_options = list(self._option_translation_key_to_key_mapping.keys())

        self.entity_description = entity_description

        super().__init__(mass, player_id, player_option)

    @catch_musicassistant_error
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option_key := self._option_translation_key_to_key_mapping.get(option):
            await self.mass.players.set_option(
                self.player_id, self.mass_option_key, option_key
            )

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_current_option = None
        # the value in that case is the key, which is always a string
        if isinstance(player_option.value, str):
            self._attr_current_option = self._option_key_to_translation_key_mapping.get(
                player_option.value
            )
