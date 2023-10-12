"""Platform to retrieve Islamic prayer times information for Home Assistant."""
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IslamicPrayerDataUpdateCoordinator
from .const import DOMAIN, NAME

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Fajr",
        translation_key="fajr",
    ),
    SensorEntityDescription(
        key="Sunrise",
        translation_key="sunrise",
    ),
    SensorEntityDescription(
        key="Dhuhr",
        translation_key="dhuhr",
    ),
    SensorEntityDescription(
        key="Asr",
        translation_key="asr",
    ),
    SensorEntityDescription(
        key="Maghrib",
        translation_key="maghrib",
    ),
    SensorEntityDescription(
        key="Isha",
        translation_key="isha",
    ),
    SensorEntityDescription(
        key="Midnight",
        translation_key="midnight",
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
