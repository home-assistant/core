"""Music Assistant Number platform."""

from typing import Any, Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.number import NumberEntity, NumberEntityDescription
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
    "add_to_queue_limit": (5, 50, EntityCategory.CONFIG),
    "add_to_queue_refill_minutes": (1, 30, EntityCategory.CONFIG),
    "boost_limit": (1, 10, EntityCategory.CONFIG),
    "boost_refill_minutes": (5, 120, EntityCategory.CONFIG),
    "skip_song_limit": (1, 5, EntityCategory.CONFIG),
    "skip_song_refill_minutes": (15, 180, EntityCategory.CONFIG),
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
        async def _add_entities() -> None:
            entities: list[MusicAssistantPartyModeNumber] = []
            if party_config := await mass.config.get_provider_config(instance_id):
                for number_key, (
                    min_val,
                    max_val,
                    category,
                ) in PARTY_MODE_NUMBERS.items():
                    if number_key not in party_config.values:
                        continue

                    entities.append(
                        MusicAssistantPartyModeNumber(
                            mass,
                            entry.runtime_data.party_config_coordinator,
                            instance_id,
                            config_key=number_key,
                            entity_description=NumberEntityDescription(
                                key=number_key,
                                translation_key=f"party_mode_{number_key}",
                                native_min_value=min_val,
                                native_max_value=max_val,
                                native_step=1,
                                entity_category=category,
                            ),
                        )
                    )
            async_add_entities(entities)

        hass.create_task(_add_entities())

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


class MusicAssistantPartyModeNumber(MusicAssistantPartyModeConfigEntity, NumberEntity):
    """Representation of a Number entity to control party mode settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        coordinator: Any,
        instance_id: str,
        config_key: str,
        entity_description: NumberEntityDescription,
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
        self._attr_native_value = None

    @override
    def _handle_coordinator_update(self) -> None:
        """Update number state."""
        if not (party_config := self.coordinator.data):
            self._attr_available = False
            super()._handle_coordinator_update()
            return

        try:
            value = party_config.get_value(self.config_key)
            if isinstance(value, (int, float, str)):
                self._attr_native_value = float(value)
            self._attr_available = True
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Error in number update: %s", err)
            self._attr_available = False

        super()._handle_coordinator_update()

    @catch_musicassistant_error
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        LOGGER.debug(
            "Setting number %s to %s for %s", self.config_key, value, self.instance_id
        )
        await self.mass.config.save_provider_config(
            provider_domain="party",
            instance_id=self.instance_id,
            values={self.config_key: int(value)},
        )
