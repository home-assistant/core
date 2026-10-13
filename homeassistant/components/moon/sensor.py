"""Support for tracking the moon phases."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .helpers import MOON_PHASES, MoonConfigEntry, moon_phase


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    async_add_entities([MoonSensorEntity(entry)], True)


class MoonSensorEntity(SensorEntity):
    """Representation of a Moon sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(MOON_PHASES)
    _attr_translation_key = "phase"

    def __init__(self, entry: MoonConfigEntry) -> None:
        """Initialize the moon sensor."""
        self._moon_data = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            name="Moon",
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self) -> None:
        """Get the time and updates the states."""
        self._attr_native_value = moon_phase(self._moon_data)
