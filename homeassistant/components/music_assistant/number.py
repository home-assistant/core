"""Music Assistant Number platform."""

import logging
from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, MusicAssistantConfigEntry
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

LOGGER = logging.getLogger(__name__)

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

PARTY_MODE_NUMBERS = {
    "add_to_queue_limit": ("mdi:playlist-plus", 5, 50, EntityCategory.CONFIG),
    "add_to_queue_refill_minutes": ("mdi:timer", 1, 30, EntityCategory.CONFIG),
    "boost_limit": ("mdi:rocket-launch", 1, 10, EntityCategory.CONFIG),
    "boost_refill_minutes": ("mdi:timer", 5, 120, EntityCategory.CONFIG),
    "skip_song_limit": ("mdi:skip-next", 1, 5, EntityCategory.CONFIG),
    "skip_song_refill_minutes": ("mdi:timer", 15, 180, EntityCategory.CONFIG),
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

    def add_party_mode(instance_id: str) -> None:
        """Handle add party mode."""
        entities: list[MusicAssistantPartyModeNumber] = [
            MusicAssistantPartyModeNumber(
                mass,
                instance_id,
                config_key=number_key,
                entity_description=NumberEntityDescription(
                    key=number_key,
                    translation_key=f"party_mode_{number_key}",
                    icon=icon,
                    native_min_value=min_val,
                    native_max_value=max_val,
                    native_step=1,
                    entity_category=category,
                ),
            )
            for number_key, (
                icon,
                min_val,
                max_val,
                category,
            ) in PARTY_MODE_NUMBERS.items()
        ]
        async_add_entities(entities)

    entry.runtime_data.party_handlers.setdefault(Platform.NUMBER, add_party_mode)


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


class MusicAssistantPartyModeNumber(NumberEntity):
    """Representation of a Number entity to control party mode settings."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mass: MusicAssistantClient,
        instance_id: str,
        config_key: str,
        entity_description: NumberEntityDescription,
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
        """Update number state."""
        try:
            party_config = await self.mass.config.get_provider_config(self.instance_id)
            value = party_config.get_value(self.config_key)
            if isinstance(value, (int, float, str)):
                self._attr_native_value = float(value)
            self._attr_available = True
        except Exception as e:  # noqa: BLE001
            LOGGER.debug("ERROR IN NUMBER UPDATE: %s", e)
            self._attr_available = False

    @catch_musicassistant_error
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.mass.config.save_provider_config(
            provider_domain="party",
            instance_id=self.instance_id,
            values={self.config_key: int(value)},
        )
