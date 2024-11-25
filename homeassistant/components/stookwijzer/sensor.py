"""Support for Stookwijzer Sensor."""

from __future__ import annotations

from datetime import timedelta

from stookwijzer import Stookwijzer

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StookwijzerSensor(client, entry)], update_before_add=True)


class StookwijzerSensor(SensorEntity):
    """Defines a Stookwijzer binary sensor."""

    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_translation_key = "advice"

    def __init__(self, client: Stookwijzer, entry: ConfigEntry) -> None:
        """Initialize a Stookwijzer device."""
        self._client = client
        self._attr_options = ["code_yellow", "code_orange", "code_red"]
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )

    async def async_update(self) -> None:
        """Update the data from the Stookwijzer handler."""
        await self._client.async_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.advice is not None

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        return self._client.advice
