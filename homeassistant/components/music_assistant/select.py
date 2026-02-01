"""Music Assistant Select platform."""

from __future__ import annotations

from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .entity import MusicAssistantPlayerOptionEntity


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
        entities: list[MusicAssistantPlayerConfigSelect] = []
        for player_option in player.player_options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.CHOICES
            ):
                entities.extend(
                    [
                        MusicAssistantPlayerConfigSelect(
                            mass, player_id, player_option=player_option
                        )
                    ]
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SELECT, add_player)


class MusicAssistantPlayerConfigSelect(MusicAssistantPlayerOptionEntity, SelectEntity):
    """Representation of a Number entity to control player provider dependent settings."""

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        super().on_player_option_update(player_option)

        self.entity_description = SelectEntityDescription(
            name=player_option.name,
            key=player_option.translation_key or "",
            translation_key=player_option.translation_key or "",
        )

        # self._attr_options = list(capability.options.values())
        if choices := player_option.choices:
            self._attr_options = [choice.id for choice in choices]

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return str(self.mass_value)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.mass.players.set_player_option(
            self.player_id, self.mass_option_id, option
        )
