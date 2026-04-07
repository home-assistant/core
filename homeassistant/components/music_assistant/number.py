"""Music Assistant Number platform."""

from __future__ import annotations

from typing import Final

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import PLAYER_OPTIONS_TRANSLATION_KEY_PREFIX
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_OPTIONS_TRANSLATION_KEYS_NUMBER: Final[list[str]] = [
    "bass",
    "dialogue_level",
    "dialogue_lift",
    "dts_dialogue_control",
    "equalizer_high",
    "equalizer_low",
    "equalizer_mid",
    "subwoofer_volume",
    "treble",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Number Entities (Player Options) from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigNumber] = []
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type
                in (
                    PlayerOptionType.INTEGER,
                    PlayerOptionType.FLOAT,
                )
                and not player_option.options  # these we map to select
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
                if translation_key not in PLAYER_OPTIONS_TRANSLATION_KEYS_NUMBER:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigNumber(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=NumberEntityDescription(
                            key=player_option.key,
                            translation_key=translation_key,
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.NUMBER, add_player)


class MusicAssistantPlayerConfigNumber(MusicAssistantPlayerOptionEntity, NumberEntity):
    """Representation of a Number entity to control player provider dependent settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        player_option: PlayerOption,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initialize MusicAssistantPlayerConfigNumber."""
        super().__init__(mass, player_id, player_option)

        self.entity_description = entity_description

    @catch_musicassistant_error
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        _value = round(value) if self.mass_type == PlayerOptionType.INTEGER else value
        await self.mass.players.set_option(
            self.player_id,
            self.mass_option_key,
            _value,
        )

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        if player_option.min_value is not None:
            self._attr_native_min_value = player_option.min_value
        if player_option.max_value is not None:
            self._attr_native_max_value = player_option.max_value
        if player_option.step is not None:
            self._attr_native_step = player_option.step

        self._attr_native_value = (
            player_option.value
            if isinstance(player_option.value, (int, float))
            else None
        )
