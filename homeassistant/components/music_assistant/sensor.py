"""Music Assistant Sensor platform."""

from __future__ import annotations

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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
        entities: list[MusicAssistantPlayerConfigSensor] = []
        for player_option in player.player_options:
            if player_option.read_only:
                entities.extend(
                    [
                        MusicAssistantPlayerConfigSensor(
                            mass, player_id, player_option=player_option
                        )
                    ]
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SENSOR, add_player)


class MusicAssistantPlayerConfigSensor(MusicAssistantPlayerOptionEntity, SensorEntity):
    """Representation of a Number entity to control player provider dependent settings."""

    def __init__(
        self, mass: MusicAssistantClient, player_id: str, player_option: PlayerOption
    ) -> None:
        """Initialize MusicAssistantPlayerConfigSensor."""
        self.player_config_type = player_option.type
        super().__init__(mass, player_id, player_option)

    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        super().on_player_option_update(player_option)

        self.entity_description = SensorEntityDescription(
            name=player_option.name,
            key=player_option.translation_key or "",
            translation_key=player_option.translation_key or "",
        )

    @property
    def native_value(self) -> int | str:
        """Return native value."""
        # MA's PlayerOptionValueType = bool | int | str.
        # but native_value only allows str | int | float | date | datetime | Decimal | None
        # convert bool to int.
        _value = self.mass_value
        if isinstance(_value, bool):
            _value = int(_value)
        return _value
