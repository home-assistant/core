"""Support for Balboa sensors."""

from __future__ import annotations

from datetime import datetime, timedelta

from pybalboa import SpaClient

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import BalboaConfigEntry
from .entity import BalboaEntity

REQUEST_FAULT_LOG_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BalboaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the spa's sensors."""
    spa = entry.runtime_data

    async def request_fault_log(now: datetime | None = None) -> None:
        """Request the most recent fault log."""
        await spa.request_fault_log()

    await request_fault_log()
    entry.async_on_unload(
        async_track_time_interval(hass, request_fault_log, REQUEST_FAULT_LOG_INTERVAL)
    )

    async_add_entities([BalboaSensorEntity(spa, "fault")])


class BalboaSensorEntity(BalboaEntity, SensorEntity):
    """Representation of a Balboa sensor entity."""

    def __init__(self, spa: SpaClient, key: str) -> None:
        """Initialize a Balboa sensor entity."""
        super().__init__(spa, key)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_translation_key = key

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the sensor."""
        if not (fault := self._client.fault):
            return None
        message = fault.message
        return f"{fault.fault_datetime.strftime('%Y-%m-%d %H:%M')}: {message} ({fault.entry_number + 1}/{fault.count})"
