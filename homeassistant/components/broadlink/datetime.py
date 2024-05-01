"""Support for Broadlink sensors."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import BroadlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink datetime."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities([BroadlinkDateTime(device)])


class BroadlinkDateTime(BroadlinkEntity, DateTimeEntity):
    """Representation of a Broadlink date and time."""

    _attr_has_entity_name = True
    _attr_native_value: datetime | None = None

    def __init__(self, device) -> None:
        """Initialize the sensor."""
        super().__init__(device)

        self._attr_unique_id = f"{device.unique_id}-datetime"

    def _update_state(self, data) -> None:
        """Update the state of the entity."""
        if data is None or "dayofweek" not in data:
            self._attr_native_value = None
        else:
            now = dt_util.now()
            device_weekday = data["dayofweek"] - 1
            this_weekday = now.weekday()

            if device_weekday != this_weekday:
                days_diff = this_weekday - device_weekday
                if days_diff < 0:
                    days_diff += 7
                now -= timedelta(days=days_diff)

            self._attr_native_value = now.replace(
                hour=data["hour"],
                minute=data["min"],
                second=data["sec"],
            )

    async def async_set_value(self, value: datetime) -> None:
        """Change the value."""
        value = dt_util.as_local(value)
        await self._device.async_request(
            self._device.api.set_time,
            hour=value.hour,
            minute=value.minute,
            second=value.second,
            day=value.weekday() + 1,
        )
        self._attr_native_value = value
        self.async_write_ha_state()
