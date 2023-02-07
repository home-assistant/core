"""This integration provides support for Stookwijzer Sensor."""
from __future__ import annotations

from datetime import timedelta

from stookwijzer import Stookwijzer

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, StookwijzerState

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

    _attr_attribution = "Data provided by stookwijzer.nu"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_translation_key = "stookwijzer"

    def __init__(self, client: Stookwijzer, entry: ConfigEntry) -> None:
        """Initialize a Stookwijzer device."""
        self._client = client
        self._attr_options = [cls.value for cls in StookwijzerState]
        self._attr_unique_id = entry.entry_id
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.state is not None

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        if self._client.state is None:
            return None
        return StookwijzerState(self._client.state).value
