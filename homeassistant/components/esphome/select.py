"""Support for esphome selects."""

from __future__ import annotations

from aioesphomeapi import EntityInfo, SelectInfo, SelectState

from homeassistant.components.assist_pipeline.select import (
    AssistPipelineSelect,
    AssistSecondaryPipelineSelect,
    VadSensitivitySelect,
)
from homeassistant.components.assist_satellite import AssistSatelliteConfiguration
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import restore_state
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NO_WAKE_WORD
from .entity import (
    EsphomeAssistEntity,
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
)
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up esphome selects based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=SelectInfo,
        entity_type=EsphomeSelect,
        state_type=SelectState,
    )

    entry_data = entry.runtime_data
    assert entry_data.device_info is not None
    if entry_data.device_info.voice_assistant_feature_flags_compat(
        entry_data.api_version
    ):
        async_add_entities(
            [
                EsphomeAssistPipelineSelect(hass, entry_data),
                EsphomeSecondaryAssistPipelineSelect(hass, entry_data),
                EsphomeVadSensitivitySelect(hass, entry_data),
                EsphomeAssistSatelliteWakeWordSelect(entry_data),
                EsphomeSecondaryAssistSatelliteWakeWordSelect(entry_data),
            ]
        )


class EsphomeSelect(EsphomeEntity[SelectInfo, SelectState], SelectEntity):
    """A select implementation for esphome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        self._attr_options = self._static_info.options

    @property
    @esphome_state_property
    def current_option(self) -> str | None:
        """Return the state of the entity."""
        state = self._state
        return None if state.missing_state else state.state

    @convert_api_error_ha_error
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._client.select_command(
            self._key, option, device_id=self._static_info.device_id
        )


class EsphomeAssistPipelineSelect(EsphomeAssistEntity, AssistPipelineSelect):
    """Pipeline selector for esphome devices."""

    def __init__(self, hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
        """Initialize a pipeline selector."""
        EsphomeAssistEntity.__init__(self, entry_data)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, self._device_info.mac_address)


class EsphomeSecondaryAssistPipelineSelect(
    EsphomeAssistEntity, AssistSecondaryPipelineSelect
):
    """Secondary pipeline selector for esphome devices."""

    def __init__(self, hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
        """Initialize a secondary pipeline selector."""
        EsphomeAssistEntity.__init__(self, entry_data)
        AssistSecondaryPipelineSelect.__init__(
            self, hass, DOMAIN, self._device_info.mac_address
        )


class EsphomeVadSensitivitySelect(EsphomeAssistEntity, VadSensitivitySelect):
    """VAD sensitivity selector for ESPHome devices."""

    def __init__(self, hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
        """Initialize a VAD sensitivity selector."""
        EsphomeAssistEntity.__init__(self, entry_data)
        VadSensitivitySelect.__init__(self, hass, self._device_info.mac_address)


class EsphomeAssistSatelliteWakeWordSelect(
    EsphomeAssistEntity, SelectEntity, restore_state.RestoreEntity
):
    """Wake word selector for esphome devices."""

    entity_description = SelectEntityDescription(
        key="wake_word",
        translation_key="wake_word",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_current_option: str | None = None
    _attr_options: list[str] = [NO_WAKE_WORD]

    def __init__(self, entry_data: RuntimeEntryData, wake_word_index: int = 0) -> None:
        """Initialize a wake word selector."""
        EsphomeAssistEntity.__init__(self, entry_data)

        unique_id_prefix = self._device_info.mac_address
        self._attr_unique_id = f"{unique_id_prefix}-wake_word"

        # name -> id
        self._wake_words: dict[str, str] = {}
        self._wake_word_index = wake_word_index

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return len(self._attr_options) > 1  # more than just NO_WAKE_WORD

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            self._attr_current_option = last_state.state

        # Update options when config is updated
        self.async_on_remove(
            self._entry_data.async_register_assist_satellite_config_updated_callback(
                self.async_satellite_config_updated
            )
        )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()

        wake_word_id = self._wake_words.get(option)
        self._entry_data.async_assist_satellite_set_wake_word(
            self._wake_word_index, wake_word_id
        )

    def async_satellite_config_updated(
        self, config: AssistSatelliteConfiguration
    ) -> None:
        """Update options with available wake words."""
        if (not config.available_wake_words) or (config.max_active_wake_words < 1):
            # No wake words
            self._wake_words.clear()
            self._attr_current_option = NO_WAKE_WORD
            self._attr_options = [NO_WAKE_WORD]
            self.async_write_ha_state()
            return

        self._wake_words = {w.wake_word: w.id for w in config.available_wake_words}
        self._attr_options = [NO_WAKE_WORD, *sorted(self._wake_words)]

        option = NO_WAKE_WORD
        if config.active_wake_words:
            for active_wake_word_id in config.active_wake_words:
                for wake_word, wake_word_id in self._wake_words.items():
                    if (wake_word_id == active_wake_word_id) and (
                        self._attr_current_option == wake_word
                    ):
                        option = wake_word
                        break

        self._attr_current_option = option
        self.async_write_ha_state()


class EsphomeSecondaryAssistSatelliteWakeWordSelect(
    EsphomeAssistSatelliteWakeWordSelect
):
    """Secondary wake word selector for esphome devices."""

    entity_description = SelectEntityDescription(
        key="wake_word_2",
        translation_key="wake_word_2",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, entry_data: RuntimeEntryData) -> None:
        """Initialize a secondary wake word selector."""
        EsphomeAssistSatelliteWakeWordSelect.__init__(self, entry_data, 1)

        unique_id_prefix = self._device_info.mac_address
        self._attr_unique_id = f"{unique_id_prefix}-wake_word-2"
