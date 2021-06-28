"""Support for Cloudflare sensors."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DATA_LAST_UPDATE, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cloudflare sensors based on a config entry."""
    unique_id = entry.unique_id

    if unique_id is None:
        unique_id = entry.entry_id

    sensors = []

    sensors.append(CloudflareLastUpdateSensor(entry.entry_id, unique_id))

    async_add_entities(sensors, True)


class CloudflareLastUpdateSensor(SensorEntity):
    """Defines a Cloudflare last update sensor."""

    _attr_device_class = DEVICE_CLASS_TIMESTAMP

    def __init__(self, entry_id: str, unique_id: str) -> None:
        """Initialize Cloudflare Last Update sensor."""
        _attr_name = "Cloudflare Last Update"
        _attr_unique_id = f"{unique_id}_last_update"
        _attr_icon = "mdi:clock-outline"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        uptime = utcnow() - timedelta(seconds=0)
        return uptime.replace(microsecond=0).isoformat()
