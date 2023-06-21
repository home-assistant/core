"""Platform to retrieve Islamic prayer times information for Home Assistant."""
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IslamicPrayerDataUpdateCoordinator
from .const import DOMAIN, NAME

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Fajr",
        name="Fajr prayer",
    ),
    SensorEntityDescription(
        key="Sunrise",
        name="Sunrise time",
    ),
    SensorEntityDescription(
        key="Dhuhr",
        name="Dhuhr prayer",
    ),
    SensorEntityDescription(
        key="Asr",
        name="Asr prayer",
    ),
    SensorEntityDescription(
        key="Maghrib",
        name="Maghrib prayer",
    ),
    SensorEntityDescription(
        key="Isha",
        name="Isha prayer",
    ),
    SensorEntityDescription(
        key="Midnight",
        name="Midnight time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Islamic prayer times sensor platform."""

    coordinator: IslamicPrayerDataUpdateCoordinator = hass.data[DOMAIN]

    async_add_entities(
        IslamicPrayerTimeSensor(coordinator, description)
        for description in SENSOR_TYPES
    )


class IslamicPrayerTimeSensor(
    CoordinatorEntity[IslamicPrayerDataUpdateCoordinator], SensorEntity
):
    """Representation of an Islamic prayer time sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IslamicPrayerDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Islamic prayer time sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]
