"""Music Assistant Switch platform."""

from typing import Any, Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import LOGGER
from .entity import (
    MusicAssistantPartyModeConfigEntity,
    MusicAssistantPlayerOptionEntity,
)
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

PARTY_MODE_SWITCHES = {
    "enable_guest_access": None,
    "karaoke_mode": None,
    "highlight_ahead": EntityCategory.CONFIG,
    "hide_back_button": EntityCategory.CONFIG,
    "show_progress_bar": EntityCategory.CONFIG,
    "enable_rate_limiting": EntityCategory.CONFIG,
    "enable_add_queue": EntityCategory.CONFIG,
    "prevent_duplicate_tracks": EntityCategory.CONFIG,
    "enable_boost": EntityCategory.CONFIG,
    "enable_skip_song": EntityCategory.CONFIG,
    "anti_burn_in": EntityCategory.CONFIG,
    "display_lyrics": EntityCategory.CONFIG,
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

    def add_party_mode(instance_id: str) -> None:
        async def _add_entities() -> None:
            entities: list[MusicAssistantPartyModeSwitch] = []
            if party_config := await mass.config.get_provider_config(instance_id):
                for switch_key, category in PARTY_MODE_SWITCHES.items():
                    if switch_key not in party_config.values:
                        continue

                    entities.append(
                        MusicAssistantPartyModeSwitch(
                            mass,
                            entry.runtime_data.party_config_coordinator,
                            instance_id,
                            config_key=switch_key,
                            entity_description=SwitchEntityDescription(
                                key=f"party_mode_{switch_key}",
                                translation_key=f"party_mode_{switch_key}",
                                entity_category=category,
                            ),
                        )
                    )
            async_add_entities(entities)

        hass.create_task(_add_entities())

    entry.runtime_data.party_handlers.setdefault(Platform.SWITCH, add_party_mode)


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


class MusicAssistantPartyModeSwitch(MusicAssistantPartyModeConfigEntity, SwitchEntity):
    """Representation of a Switch entity to control party mode settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        coordinator: Any,
        instance_id: str,
        config_key: str,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            mass=mass,
            coordinator=coordinator,
            instance_id=instance_id,
            unique_id_suffix=config_key,
        )
        self.config_key = config_key
        self.entity_description = entity_description
        self._attr_is_on = None

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not (party_config := self.coordinator.data):
            self._attr_available = False
            super()._handle_coordinator_update()
            return

        try:
            self._attr_is_on = bool(party_config.get_value(self.config_key))
            self._attr_available = True
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Error in switch update: %s", err)
            self._attr_available = False

        super()._handle_coordinator_update()

    @catch_musicassistant_error
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle turn on command."""
        await self._async_set_state(True)

    @catch_musicassistant_error
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle turn off command."""
        await self._async_set_state(False)

    async def _async_set_state(self, state: bool) -> None:
        """Set state."""
        LOGGER.debug(
            "Setting switch %s to %s for %s", self.config_key, state, self.instance_id
        )
        await self.mass.config.save_provider_config(
            provider_domain="party",
            instance_id=self.instance_id,
            values={self.config_key: state},
        )
