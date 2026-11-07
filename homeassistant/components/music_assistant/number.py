"""Music Assistant Number platform."""

from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import MediaType
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import PLAYER_SETTINGS_SCHEMA_VERSION
from .entity import MusicAssistantEntity, MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_OPTIONS_NUMBER: Final[dict[str, bool]] = {
    # translation_key: enabled_by_default
    "bass": True,
    "dialogue_level": False,
    "dialogue_lift": False,
    "dts_dialogue_control": False,
    "equalizer_high": False,
    "equalizer_low": False,
    "equalizer_mid": False,
    "subwoofer_volume": True,
    "treble": True,
}


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
        entities: list[NumberEntity] = []
        assert mass.server_info  # for type checking
        # older servers lack the command, so their players keep only the option numbers;
        # the queue itself may still be missing, the server adds it after the player
        if mass.server_info.schema_version >= PLAYER_SETTINGS_SCHEMA_VERSION:
            entities.append(MusicAssistantQueuePlaybackSpeed(mass, player_id))
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
                # we ignore entities with unknown translation keys.
                if player_option.translation_key not in PLAYER_OPTIONS_NUMBER:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigNumber(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=NumberEntityDescription(
                            key=player_option.key,
                            translation_key=player_option.translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_NUMBER[
                                player_option.translation_key
                            ],
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.NUMBER, add_player)


class MusicAssistantPlayerConfigNumber(MusicAssistantPlayerOptionEntity, NumberEntity):
    """Representation of a Number entity to control player settings."""

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
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        _value = round(value) if self.mass_type == PlayerOptionType.INTEGER else value
        await self.mass.players.set_option(
            self.player_id,
            self.mass_option_key,
            _value,
        )

    @override
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


class MusicAssistantQueuePlaybackSpeed(MusicAssistantEntity, NumberEntity):
    """Playback speed of the item playing in the player's own queue."""

    entity_description = NumberEntityDescription(
        key="queue_playback_speed",
        translation_key="queue_playback_speed",
        native_min_value=0.5,
        native_max_value=3.0,
        native_step=0.05,
        entity_registry_enabled_default=False,
    )

    @property
    @override
    def available(self) -> bool:
        """Return if the current item is one whose speed can change."""
        if not super().available:
            return False
        queue = self.mass.player_queues.get(self.player_id)
        current_item = queue.current_item if queue else None
        media_item = current_item.media_item if current_item else None
        # the server only changes the speed of audiobooks and podcast episodes
        return media_item is not None and media_item.media_type in (
            MediaType.AUDIOBOOK,
            MediaType.PODCAST_EPISODE,
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the playback speed of the queue."""
        if (queue := self.mass.player_queues.get(self.player_id)) is None:
            return None
        return queue.playback_speed

    @catch_musicassistant_error
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the playback speed of the playing item."""
        await self.mass.player_queues.set_playback_speed(self.player_id, value)
