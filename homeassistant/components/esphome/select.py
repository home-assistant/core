"""Support for esphome selects."""

from __future__ import annotations

from aioesphomeapi import EntityInfo, SelectInfo, SelectState

from homeassistant.components.assist_pipeline.select import (
    AssistPipelineSelect,
    VadSensitivitySelect,
)
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import (
    EsphomeAssistEntity,
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
)
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ESPHomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
                EsphomeVadSensitivitySelect(hass, entry_data),
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
        self._client.select_command(self._key, option)


class EsphomeAssistPipelineSelect(EsphomeAssistEntity, AssistPipelineSelect):
    """Pipeline selector for esphome devices."""

    def __init__(self, hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
        """Initialize a pipeline selector."""
        EsphomeAssistEntity.__init__(self, entry_data)
        AssistPipelineSelect.__init__(self, hass, DOMAIN, self._device_info.mac_address)


class EsphomeVadSensitivitySelect(EsphomeAssistEntity, VadSensitivitySelect):
    """VAD sensitivity selector for VoIP devices."""

    def __init__(self, hass: HomeAssistant, entry_data: RuntimeEntryData) -> None:
        """Initialize a VAD sensitivity selector."""
        EsphomeAssistEntity.__init__(self, entry_data)
        VadSensitivitySelect.__init__(self, hass, self._device_info.mac_address)
