"""This integration provides support for Stookwijzer Binary Sensor."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from stookwijzer import Stookwijzer

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_STOOKWIJZER, DOMAIN

SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer binary sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StookwijzerBinarySensor(client, entry)], update_before_add=True)


class StookwijzerBinarySensor(BinarySensorEntity):
    """Defines a Stookwijzer binary sensor."""

    _attr_attribution = "Data provided by stookwijzer.nu"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True

    def __init__(self, client: Stookwijzer, entry: ConfigEntry) -> None:
        """Initialize a Stookwijzer device."""
        self._client = client
        self._attrs: dict[str, Any] = {}
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}")},
            name="Stookwijzer",
            manufacturer="stookwijzer.nu",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.stookwijzer.nu",
        )

    def update(self) -> None:
        """Update the data from the Stookwijzer handler."""
        self._client.update()
        self._attr_is_on = self._client.state in ("Rood", "Oranje")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        self._attrs[ATTR_STOOKWIJZER] = self._client.state
        return self._attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._client.state is not None
