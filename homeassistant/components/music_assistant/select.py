"""Music Assistant select platform."""

from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import LOGGER
from .entity import MusicAssistantPartyModeEntity, MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_OPTIONS_SELECT: Final[dict[str, bool]] = {
    # translation_key: enabled_by_default
    "dimmer": False,
    "equalizer_mode": False,
    "link_audio_delay": True,
    "link_audio_quality": False,
    "link_control": False,
    "sleep": False,
    "surround_decoder_type": False,
    "tone_control_mode": True,
}

PARTY_MODE_SELECTS = {
    "player": None,
    "request_badge_color": EntityCategory.CONFIG,
    "boost_badge_color": EntityCategory.CONFIG,
}

BADGE_COLORS = {
    "2d6a4f": "#2D6A4F",
    "b55522": "#B55522",
    "e91e63": "#E91E63",
    "f06292": "#F06292",
    "9c27b0": "#9C27B0",
    "673ab7": "#673AB7",
    "3f51b5": "#3F51B5",
    "00bcd4": "#00BCD4",
    "009688": "#009688",
    "4caf50": "#4CAF50",
    "8bc34a": "#8BC34A",
    "e64a19": "#E64A19",
    "ffc107": "#FFC107",
    "ffeb3b": "#FFEB3B",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Select Entities (Player Options) from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigSelect] = []
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type
                != PlayerOptionType.BOOLEAN  # these always go to switch
                and player_option.options
            ):
                # We ignore entities with unknown
                # translation key for the base name.
                # However, we accept a non-available
                # translation_key in strings.json for the
                # entity's state, as these are oftentimes
                # dynamically created, dependent on a
                # specific player and might not be known to
                # the provider developer. In that case, the
                # frontend falls back to showing the state's
                # bare translation key.
                if player_option.translation_key not in PLAYER_OPTIONS_SELECT:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigSelect(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=SelectEntityDescription(
                            key=player_option.key,
                            translation_key=player_option.translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_SELECT[
                                player_option.translation_key
                            ],
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.SELECT, add_player)

    def add_party_mode(instance_id: str) -> None:
        async def _add_entities() -> None:
            entities: list[MusicAssistantPartyModeSelect] = []
            if party_config := await mass.config.get_provider_config(instance_id):
                for select_key, category in PARTY_MODE_SELECTS.items():
                    if select_key not in party_config.values:
                        continue

                    entities.append(
                        MusicAssistantPartyModeSelect(
                            mass,
                            instance_id,
                            config_key=select_key,
                            entity_description=SelectEntityDescription(
                                key=f"party_mode_{select_key}",
                                translation_key=f"party_mode_{select_key}"
                                if select_key != "player"
                                else "party_mode_party_player",
                                entity_category=category,
                            ),
                        )
                    )
            async_add_entities(entities)

        hass.create_task(_add_entities())

    entry.runtime_data.party_handlers.setdefault(Platform.SELECT, add_party_mode)


class MusicAssistantPlayerConfigSelect(MusicAssistantPlayerOptionEntity, SelectEntity):
    """Representation of a select entity to control player settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        player_option: PlayerOption,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize MusicAssistantPlayerConfigSelect."""
        # this was verified already in the entry callback
        assert player_option.options is not None
        # we have to define the dicts before initializing the parent, as this
        # then calls self.on_player_option_update
        self._option_translation_key_to_key_mapping = {
            option.translation_key: option.key for option in player_option.options
        }
        self._option_key_to_translation_key_mapping = {
            option.key: option.translation_key for option in player_option.options
        }

        super().__init__(mass, player_id, player_option)

        self.entity_description = entity_description

        self._attr_options = list(self._option_translation_key_to_key_mapping.keys())

    @catch_musicassistant_error
    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.mass.players.set_option(
            self.player_id,
            self.mass_option_key,
            self._option_translation_key_to_key_mapping[option],
        )

    @override
    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_current_option = (
            self._option_key_to_translation_key_mapping.get(player_option.value)
            if isinstance(player_option.value, str)
            else None
        )


class MusicAssistantPartyModeSelect(MusicAssistantPartyModeEntity, SelectEntity):
    """Representation of a select entity to control party mode settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        instance_id: str,
        config_key: str,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(mass, instance_id, unique_id_suffix=config_key)
        self.config_key = config_key
        self.entity_description = entity_description
        if self.config_key != "player":
            self._attr_options = list(BADGE_COLORS.keys())
        else:
            self._attr_options = []
        self._option_name_to_id: dict[str, str] = {}
        self._option_id_to_name: dict[str, str] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        if self.config_key == "player":
            self.async_on_remove(
                self.mass.subscribe(
                    self._on_player_update,
                    (
                        EventType.PLAYER_ADDED,
                        EventType.PLAYER_REMOVED,
                        EventType.PLAYER_UPDATED,
                    ),
                )
            )

    async def _on_player_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        await self.async_on_update()
        self.async_write_ha_state()

    @override
    async def async_on_update(self) -> None:
        """Update select state."""
        try:
            if self.config_key == "player":
                players = sorted(
                    self.mass.players,
                    key=lambda p: p.name.lower(),
                )
                self._option_name_to_id = {"Auto": "auto"}
                self._option_id_to_name = {"auto": "Auto"}
                for p in players:
                    self._option_name_to_id[p.name] = p.player_id
                    self._option_id_to_name[p.player_id] = p.name
                self._attr_options = list(self._option_name_to_id.keys())

            party_config = await self.mass.config.get_provider_config(self.instance_id)
            value = party_config.get_value(self.config_key)
            if self.config_key == "player":
                self._attr_current_option = self._option_id_to_name.get(
                    str(value), "Auto"
                )
            elif value and isinstance(value, str):
                # value is hex, strip the "#" and lowercase it
                self._attr_current_option = value.replace("#", "").lower()
            self._attr_available = True
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Error in select update: %s", err)
            self._attr_available = False

    @catch_musicassistant_error
    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if self.config_key == "player":
            value = self._option_name_to_id.get(option, "auto")
        else:
            value = BADGE_COLORS[option]

        LOGGER.debug(
            "Setting select %s to %s for %s", self.config_key, value, self.instance_id
        )
        await self.mass.config.save_provider_config(
            provider_domain="party",
            instance_id=self.instance_id,
            values={self.config_key: value},
        )
