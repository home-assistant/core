"""Music Assistant Switch platform."""

from typing import Any, Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import DOMAIN, LOGGER
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
        """Handle add party mode."""
        entities: list[MusicAssistantPartyModeSwitch] = [
            MusicAssistantPartyModeSwitch(
                mass,
                instance_id,
                config_key=switch_key,
                entity_description=SwitchEntityDescription(
                    key=f"party_mode_{switch_key}",
                    translation_key=f"party_mode_{switch_key}",
                    icon=icon,
                    entity_category=category,
                ),
            )
            for switch_key, (icon, category) in PARTY_MODE_SWITCHES.items()
        ]
        async_add_entities(entities)

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


PARTY_MODE_SWITCHES = {
    "enable_guest_access": ("mdi:account-group", None),
    "karaoke_mode": ("mdi:microphone", None),
    "highlight_ahead": ("mdi:format-color-highlight", EntityCategory.CONFIG),
    "hide_back_button": ("mdi:arrow-left-box", EntityCategory.CONFIG),
    "show_progress_bar": ("mdi:progress-clock", EntityCategory.CONFIG),
    "enable_rate_limiting": ("mdi:speedometer", EntityCategory.CONFIG),
    "enable_add_queue": ("mdi:playlist-plus", EntityCategory.CONFIG),
    "prevent_duplicate_tracks": ("mdi:playlist-check", EntityCategory.CONFIG),
    "enable_boost": ("mdi:rocket-launch", EntityCategory.CONFIG),
    "enable_skip_song": ("mdi:skip-next", EntityCategory.CONFIG),
    "anti_burn_in": ("mdi:television-shimmer", EntityCategory.CONFIG),
    "display_lyrics": ("mdi:script-text", EntityCategory.CONFIG),
}


class MusicAssistantPartyModeSwitch(SwitchEntity):
    """Representation of a Switch entity to control party mode settings."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mass: MusicAssistantClient,
        instance_id: str,
        config_key: str,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize."""
        self.mass = mass
        self.instance_id = instance_id
        self.config_key = config_key
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id)},
            name="Party Mode Plugin",
            manufacturer="Music Assistant",
        )
        self._attr_unique_id = f"{instance_id}_{config_key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self.async_on_update()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update,
                EventType.PROVIDERS_UPDATED,
            )
        )

    async def __on_mass_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        await self.async_on_update()
        self.async_write_ha_state()

    @catch_musicassistant_error
    async def async_on_update(self) -> None:
        """Update switch state."""
        try:
            party_config = await self.mass.config.get_provider_config(self.instance_id)
            self._attr_is_on = bool(party_config.get_value(self.config_key))
            self._attr_available = True
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Error in switch update: %s", err)
            self._attr_available = False

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
