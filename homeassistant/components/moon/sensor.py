"""Support for tracking the moon phases."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .helpers import MOON_PHASES, MoonData, async_get_moon_data, moon_phase


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    moon_data = await async_get_moon_data(hass)
    async_add_entities([MoonSensorEntity(entry, moon_data)], True)


class MoonSensorEntity(SensorEntity):
    """Representation of a Moon sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(MOON_PHASES)
    _attr_translation_key = "phase"

    def __init__(self, entry: ConfigEntry, moon_data: MoonData) -> None:
        """Initialize the moon sensor."""
        self._moon_data = moon_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            translation_key="moon",
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self) -> None:
        """Get the time and updates the states."""
        self._attr_native_value = moon_phase(self._moon_data)
