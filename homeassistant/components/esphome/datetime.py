"""Support for esphome datetimes."""

from __future__ import annotations

from datetime import datetime

from aioesphomeapi import DateTimeInfo, DateTimeState

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up esphome datetimes based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=DateTimeInfo,
        entity_type=EsphomeDateTime,
        state_type=DateTimeState,
    )


class EsphomeDateTime(EsphomeEntity[DateTimeInfo, DateTimeState], DateTimeEntity):
    """A datetime implementation for esphome."""

    @property
    @esphome_state_property
    def native_value(self) -> datetime | None:
        """Return the state of the entity."""
        state = self._state
        if state.missing_state:
            return None
        return datetime(
            state.year,
            state.month,
            state.day,
            state.hour,
            state.minute,
            state.second,
            tzinfo=dt_util.DEFAULT_TIME_ZONE,
        )

    async def async_set_value(self, value: datetime) -> None:
        """Update the current datetime."""
        tz_value = value.astimezone(dt_util.DEFAULT_TIME_ZONE)
        self._client.datetime_command(
            self._key,
            tz_value.year,
            tz_value.month,
            tz_value.day,
            tz_value.hour,
            tz_value.minute,
            tz_value.second,
        )
