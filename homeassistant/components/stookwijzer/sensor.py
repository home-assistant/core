"""Support for Stookwijzer Sensor."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StookwijzerConfigEntry, StookwijzerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StookwijzerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer sensor from a config entry."""
    async_add_entities([StookwijzerSensor(entry)])


class StookwijzerSensor(CoordinatorEntity[StookwijzerCoordinator], SensorEntity):
    """Defines a Stookwijzer binary sensor."""

    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_has_entity_name = True
    _attr_translation_key = "advice"

    def __init__(self, entry: StookwijzerConfigEntry) -> None:
        """Initialize a Stookwijzer device."""
        super().__init__(entry.runtime_data)
        self._client = entry.runtime_data.client
        self._attr_options = ["code_yellow", "code_orange", "code_red"]
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        return self._client.advice
