"""Music Assistant Number platform."""

from __future__ import annotations

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

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
        for player_option in player.player_options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.NUMBER
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

    def __init__(
        self, mass: MusicAssistantClient, player_id: str, player_option: PlayerOption
    ) -> None:
        """Initialize MusicAssistantPlayerConfigNumber."""
        super().__init__(mass, player_id, player_option)
        self._attr_native_min_value = player_option.min_value or 0
        self._attr_native_max_value = player_option.max_value or 100
        self._attr_native_step = player_option.step or 1

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        assert isinstance(self.mass_value, int | float)
        return self.mass_value

    @catch_musicassistant_error
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.mass.players.set_player_option(
            self.player_id, self.mass_option_id, int(value)
        )

    def update_description(self, option: PlayerOption) -> None:
        """Update switch's description."""
        self.entity_description = NumberEntityDescription(
            name=option.name,
            key=option.translation_key or "",
            translation_key=option.translation_key or "",
        )
