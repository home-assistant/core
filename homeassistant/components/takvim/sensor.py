"""Prayer time sensors for the Takvim integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, PRAYERS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up prayer time sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [PrayerTimeSensor(coordinator, prayer) for prayer in PRAYERS]

    async_add_entities(entities)


class PrayerTimeSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing a single prayer time."""

    def __init__(self, coordinator, prayer: str) -> None:
        """Initialize the prayer time sensor."""
        super().__init__(coordinator)

        self.prayer = prayer

        self._attr_name = prayer.title()
        self._attr_unique_id = f"prayer_time_{coordinator.district_id}_{prayer}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the prayer time as a datetime in Europe/Berlin."""
        return self.coordinator.data.get(self.prayer)
