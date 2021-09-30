"""Support for esphome selects."""
from __future__ import annotations

from typing import cast

from aioesphomeapi import SelectInfo, SelectState
import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry

ICON_SCHEMA = vol.Schema(cv.icon)


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


# https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
# pylint: disable=invalid-overridden-method


class EsphomeSelect(EsphomeEntity[SelectInfo, SelectState], SelectEntity):
    """A select implementation for esphome."""

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if not self._static_info.icon:
            return None
        return cast(str, ICON_SCHEMA(self._static_info.icon))

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self._static_info.options

    @esphome_state_property
    def current_option(self) -> str | None:
        """Return the state of the entity."""
        if self._state.missing_state:
            return None
        return self._state.state

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._client.select_command(self._static_info.key, option)
