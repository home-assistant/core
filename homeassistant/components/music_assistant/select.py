"""Music Assistant Select platform."""

from __future__ import annotations

from music_assistant_client import MusicAssistantClient
from music_assistant_models.player import PlayerOption

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
        entities: list[MusicAssistantPlayerConfigSelect] = []
        for player_option in player.options:
            if not player_option.read_only and player_option.options:
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

    def __init__(
        self, mass: MusicAssistantClient, player_id: str, player_option: PlayerOption
    ) -> None:
        """Initialize MusicAssistantPlayerConfigSelect."""
        self._option_name_key_mapping: dict[str, str] = {}
        self._update_available_options(player_option)
        super().__init__(mass, player_id, player_option)

    def _update_available_options(self, player_option: PlayerOption) -> None:
        """Update selectable options."""
        if player_option.options is not None:
            self._option_name_key_mapping = {
                option.name: option.key for option in player_option.options
            }
            self._attr_options = list(self._option_name_key_mapping.keys())

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        super().on_player_option_update(player_option)

        self.entity_description = SelectEntityDescription(
            name=player_option.name,
            key=player_option.key,
            translation_key=player_option.translation_key or player_option.name,
        )

        self._update_available_options(player_option)

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return next(
            (
                option_name
                for option_name, option_key in self._option_name_key_mapping.items()
                if option_key == self.mass_value
            ),
            None,
        )

    @catch_musicassistant_error
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if _option_key := self._option_name_key_mapping.get(option):
            await self.mass.players.set_option(
                self.player_id, self.mass_option_key, _option_key
            )
