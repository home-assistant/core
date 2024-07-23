"""Support for esphome times."""

from __future__ import annotations

from datetime import time

from aioesphomeapi import TimeInfo, TimeState

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up esphome times based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=TimeInfo,
        entity_type=EsphomeTime,
        state_type=TimeState,
    )


class EsphomeTime(EsphomeEntity[TimeInfo, TimeState], TimeEntity):
    """A time implementation for esphome."""

    @property
    @esphome_state_property
    def native_value(self) -> time | None:
        """Return the state of the entity."""
        state = self._state
        if state.missing_state:
            return None
        return time(state.hour, state.minute, state.second)

    async def async_set_value(self, value: time) -> None:
        """Update the current time."""
        self._client.time_command(self._key, value.hour, value.minute, value.second)
