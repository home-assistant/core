"""Music Assistant Number platform."""

from __future__ import annotations

from music_assistant_models.player import (
    PlayerOption,
    PlayerOptionType,
    PlayerOptionTypeMap,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
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
                entities.extend(
                    [
                        MusicAssistantPlayerConfigNumber(
                            mass, player_id, player_option=player_option
                        )
                    ]
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.NUMBER, add_player)


class MusicAssistantPlayerConfigNumber(MusicAssistantPlayerOptionEntity, NumberEntity):
    """Representation of a Number entity to control player provider dependent settings."""

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not isinstance(self.mass_value, int | float):
            return None
        return self.mass_value

    @catch_musicassistant_error
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.mass.players.set_option(
            self.player_id,
            self.mass_option_key,
            PlayerOptionTypeMap[self.mass_type](value),
        )

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        super().on_player_option_update(player_option)

        self.entity_description = NumberEntityDescription(
            name=player_option.name,
            key=player_option.key,
            translation_key=player_option.translation_key or player_option.name,
        )

        if min_value := player_option.min_value:
            self._attr_native_min_value = min_value
        if max_value := player_option.max_value:
            self._attr_native_max_value = max_value
        if step := player_option.step:
            self._attr_native_step = step
