"""Support for Stookalert Binary Sensor."""
from __future__ import annotations

from datetime import timedelta

import stookalert

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PROVINCE, DOMAIN

SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookalert binary sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StookalertBinarySensor(client, entry)], update_before_add=True)


class StookalertBinarySensor(BinarySensorEntity):
    """Defines a Stookalert binary sensor."""

    _attr_attribution = "Data provided by rivm.nl"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, client: stookalert.stookalert, entry: ConfigEntry) -> None:
        """Initialize a Stookalert device."""
        self._client = client
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}")},
            name=f"Stookalert {entry.data[CONF_PROVINCE]}",
            manufacturer="RIVM",
            model="Stookalert",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.rivm.nl/stookalert",
        )

    def update(self) -> None:
        """Update the data from the Stookalert handler."""
        self._client.get_alerts()
        self._attr_is_on = self._client.state == 1
