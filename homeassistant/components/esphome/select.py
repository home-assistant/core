"""Support for esphome selects."""
from __future__ import annotations

from aioesphomeapi import SelectInfo, SelectState

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up esphome selects based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="select",
        info_type=SelectInfo,
        entity_type=EsphomeSelect,
        state_type=SelectState,
    )


class EsphomeSelect(EsphomeEntity[SelectInfo, SelectState], SelectEntity):
    """A select implementation for esphome."""

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self._static_info.options

    @property
    @esphome_state_property
    def current_option(self) -> str | None:
        """Return the state of the entity."""
        if self._state.missing_state:
            return None
        return self._state.state

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._client.select_command(self._static_info.key, option)
