"""Music Assistant Switch platform."""

from __future__ import annotations

from typing import Any, Final

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import PLAYER_OPTIONS_TRANSLATION_KEY_PREFIX
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_OPTIONS_SWITCH: Final[dict[str, bool]] = {
    # translation_key: enabled_by_default
    "adaptive_drc": False,
    "bass_extension": False,
    "clear_voice": False,
    "enhancer": True,
    "extra_bass": False,
    "party_mode": False,
    "pure_direct": True,
    "speaker_a": True,
    "speaker_b": True,
    "surround_3d": False,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Switch Entities (Player Options) from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigSwitch] = []
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.BOOLEAN
            ):
                # the MA translation key must have the format player_options.<translation key>
                # we ignore entities with unknown translation keys.
                if (
                    player_option.translation_key is None
                    or not player_option.translation_key.startswith(
                        PLAYER_OPTIONS_TRANSLATION_KEY_PREFIX
                    )
                ):
                    continue
                translation_key = player_option.translation_key[
                    len(PLAYER_OPTIONS_TRANSLATION_KEY_PREFIX) :
                ]
                if translation_key not in PLAYER_OPTIONS_SWITCH:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigSwitch(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=SwitchEntityDescription(
                            key=player_option.key,
                            translation_key=translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_SWITCH[
                                translation_key
                            ],
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SWITCH, add_player)


class MusicAssistantPlayerConfigSwitch(MusicAssistantPlayerOptionEntity, SwitchEntity):
    """Representation of a Switch entity to control player provider dependent settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        player_option: PlayerOption,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize MusicAssistantPlayerConfigSwitch."""
        super().__init__(mass, player_id, player_option)

        self.entity_description = entity_description

    @catch_musicassistant_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle turn on command."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, True)

    @catch_musicassistant_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle turn off command."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, False)

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_is_on = (
            player_option.value if isinstance(player_option.value, bool) else None
        )
