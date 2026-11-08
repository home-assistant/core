"""Music Assistant select platform."""

from typing import TYPE_CHECKING, Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.dsp import DSPConfig, DSPConfigPreset
from music_assistant_models.enums import EventType, PlayerType
from music_assistant_models.event import MassEvent
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .entity import MusicAssistantEntity, MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error

PLAYER_SETTINGS_SCHEMA_VERSION: Final = 101

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant Select Entities (Player Options) from Config Entry."""
    mass = entry.runtime_data.mass
    if TYPE_CHECKING:
        assert mass.server_info is not None
    # older servers drop the preset when DSP is switched, so they get no preset select
    dsp_supported = mass.server_info.schema_version >= PLAYER_SETTINGS_SCHEMA_VERSION

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[SelectEntity] = []
        # a group applies the DSP of each member, it has none of its own
        if dsp_supported and player.type is not PlayerType.GROUP:
            entities.append(MusicAssistantDspPresetSelect(mass, player_id))
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


class MusicAssistantDspPresetSelect(MusicAssistantEntity, SelectEntity):
    """Select which DSP preset a player uses."""

    entity_description = SelectEntityDescription(
        key="dsp_preset",
        translation_key="dsp_preset",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    )

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MusicAssistantDspPresetSelect."""
        super().__init__(mass, player_id)
        self._dsp_presets: list[DSPConfigPreset] = []
        self._dsp_config: DSPConfig | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Load the presets and the player's DSP config and follow their changes."""
        self._dsp_presets = await self.mass.config.get_dsp_preset()
        self._dsp_config = await self.mass.config.get_player_dsp_config(self.player_id)
        await super().async_added_to_hass()
        self.async_on_remove(
            self.mass.subscribe(
                self._on_dsp_config_updated,
                EventType.PLAYER_DSP_CONFIG_UPDATED,
                self.player_id,
            )
        )
        self.async_on_remove(
            self.mass.subscribe(
                self._on_dsp_presets_updated, EventType.DSP_PRESETS_UPDATED
            )
        )

    @property
    @override
    def available(self) -> bool:
        """Return if there are presets to choose from."""
        return super().available and bool(self._dsp_presets)

    @property
    @override
    def options(self) -> list[str]:
        """Return the names of the DSP presets."""
        return [preset.name for preset in self._dsp_presets]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the preset of the player's DSP settings, also while DSP is off."""
        if self._dsp_config is None:
            return None
        return next(
            (
                preset.name
                for preset in self._dsp_presets
                if preset.preset_id == self._dsp_config.preset_id
            ),
            None,
        )

    @catch_musicassistant_error
    @override
    async def async_select_option(self, option: str) -> None:
        """Apply the chosen DSP preset to the player."""
        preset = next(preset for preset in self._dsp_presets if preset.name == option)
        if TYPE_CHECKING:
            # stored presets always have an id
            assert preset.preset_id is not None
        await self.mass.config.apply_dsp_preset(self.player_id, preset.preset_id)

    def _on_dsp_config_updated(self, event: MassEvent) -> None:
        self._dsp_config = DSPConfig.from_dict(event.data)
        self.async_write_ha_state()

    def _on_dsp_presets_updated(self, event: MassEvent) -> None:
        self._dsp_presets = [DSPConfigPreset.from_dict(preset) for preset in event.data]
        self.async_write_ha_state()
