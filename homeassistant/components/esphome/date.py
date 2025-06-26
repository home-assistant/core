"""Support for esphome dates."""

from __future__ import annotations

from datetime import date
from functools import partial

from aioesphomeapi import DateInfo, DateState

from homeassistant.components.date import DateEntity

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry

PARALLEL_UPDATES = 0


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


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=DateInfo,
    entity_type=EsphomeDate,
    state_type=DateState,
)
