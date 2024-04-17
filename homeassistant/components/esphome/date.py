"""Support for esphome dates."""

from __future__ import annotations

from datetime import date

from aioesphomeapi import DateInfo, DateState

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up esphome dates based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=DateInfo,
        entity_type=EsphomeDate,
        state_type=DateState,
    )


class EsphomeDate(EsphomeEntity[DateInfo, DateState], DateEntity):
    """A date implementation for esphome."""

    @property
    @esphome_state_property
    def native_value(self) -> date | None:
        """Return the state of the entity."""
        state = self._state
        if state.missing_state:
            return None
        return date(state.year, state.month, state.day)

    async def async_set_value(self, value: date) -> None:
        """Update the current date."""
        self._client.date_command(self._key, value.year, value.month, value.day)
