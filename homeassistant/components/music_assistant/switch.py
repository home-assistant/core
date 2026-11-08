"""Music Assistant Switch platform."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType
from music_assistant_models.player_queue import PlayerQueue

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import PLAYER_SETTINGS_SCHEMA_VERSION
from .entity import MusicAssistantEntity, MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error


@dataclass(frozen=True, kw_only=True)
class MusicAssistantQueueSwitchDescription(SwitchEntityDescription):
    """Describes a switch for a setting of a player's queue."""

    is_on_fn: Callable[[PlayerQueue], bool]
    set_fn: Callable[[MusicAssistantClient, str, bool], Awaitable[None]]


QUEUE_SWITCHES: Final = (
    MusicAssistantQueueSwitchDescription(
        key="queue_crossfade",
        translation_key="queue_crossfade",
        is_on_fn=lambda queue: queue.crossfade_enabled,
        set_fn=lambda mass, queue_id, enabled: mass.player_queues.crossfade(
            queue_id, enabled
        ),
    ),
    MusicAssistantQueueSwitchDescription(
        key="queue_autoplay",
        translation_key="queue_autoplay",
        is_on_fn=lambda queue: queue.autoplay_enabled,
        set_fn=lambda mass, queue_id, enabled: mass.player_queues.autoplay(
            queue_id, enabled
        ),
    ),
)

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
        entities: list[SwitchEntity] = []
        if TYPE_CHECKING:
            assert mass.server_info is not None
        # older servers lack the commands, so their players keep only the option switches;
        # the queue itself may still be missing, the server adds it after the player
        if mass.server_info.schema_version >= PLAYER_SETTINGS_SCHEMA_VERSION:
            entities.extend(
                MusicAssistantQueueSwitch(mass, player_id, description)
                for description in QUEUE_SWITCHES
            )
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.BOOLEAN
            ):
                # we ignore entities with unknown translation keys.
                if player_option.translation_key not in PLAYER_OPTIONS_SWITCH:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigSwitch(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=SwitchEntityDescription(
                            key=player_option.key,
                            translation_key=player_option.translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_SWITCH[
                                player_option.translation_key
                            ],
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SWITCH, add_player)


class MusicAssistantPlayerConfigSwitch(MusicAssistantPlayerOptionEntity, SwitchEntity):
    """Representation of a Switch entity to control player settings."""

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
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle turn on command."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, True)

    @catch_musicassistant_error
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle turn off command."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, False)

    @override
    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_is_on = (
            player_option.value if isinstance(player_option.value, bool) else None
        )


class MusicAssistantQueueSwitch(MusicAssistantEntity, SwitchEntity):
    """Switch for a setting of the player's own queue."""

    entity_description: MusicAssistantQueueSwitchDescription

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        entity_description: MusicAssistantQueueSwitchDescription,
    ) -> None:
        """Initialize MusicAssistantQueueSwitch."""
        super().__init__(mass, player_id)
        self.entity_description = entity_description

    @property
    @override
    def available(self) -> bool:
        """Return if the player and its queue are available."""
        return (
            super().available
            and self.mass.player_queues.get(self.player_id) is not None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return if the queue setting is on."""
        if (queue := self.mass.player_queues.get(self.player_id)) is None:
            return None
        return self.entity_description.is_on_fn(queue)

    @catch_musicassistant_error
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the queue setting on."""
        await self.entity_description.set_fn(self.mass, self.player_id, True)

    @catch_musicassistant_error
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the queue setting off."""
        await self.entity_description.set_fn(self.mass, self.player_id, False)
