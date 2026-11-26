"""Platform to retrieve Islamic prayer times information for Home Assistant."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import (
    IslamicPrayerDataUpdateCoordinator,
    IslamicPrayerTimesConfigEntry,
)

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


@dataclass(frozen=True, kw_only=True)
class IslamicPrayerContextSensorDescription(SensorEntityDescription):
    """Describe a current or next prayer sensor."""

    value_fn: Callable[[IslamicPrayerDataUpdateCoordinator], str | datetime | None]
    requires_current: bool = False


PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]
CONTEXT_SENSOR_TYPES: tuple[IslamicPrayerContextSensorDescription, ...] = (
    IslamicPrayerContextSensorDescription(
        key="current_prayer",
        translation_key="current_prayer",
        device_class=SensorDeviceClass.ENUM,
        options=[*PRAYERS, "between_prayers"],
        value_fn=lambda coordinator: (
            window.name.lower()
            if (window := coordinator.current_prayer)
            else "between_prayers"
        ),
    ),
    IslamicPrayerContextSensorDescription(
        key="current_prayer_started",
        translation_key="current_prayer_started",
        device_class=SensorDeviceClass.TIMESTAMP,
        requires_current=True,
        value_fn=lambda coordinator: (
            window.start if (window := coordinator.current_prayer) else None
        ),
    ),
    IslamicPrayerContextSensorDescription(
        key="current_prayer_ends",
        translation_key="current_prayer_ends",
        device_class=SensorDeviceClass.TIMESTAMP,
        requires_current=True,
        value_fn=lambda coordinator: (
            window.end if (window := coordinator.current_prayer) else None
        ),
    ),
    IslamicPrayerContextSensorDescription(
        key="next_prayer",
        translation_key="next_prayer",
        device_class=SensorDeviceClass.ENUM,
        options=PRAYERS,
        value_fn=lambda coordinator: (
            window.name.lower() if (window := coordinator.next_prayer) else None
        ),
    ),
    IslamicPrayerContextSensorDescription(
        key="next_prayer_starts",
        translation_key="next_prayer_starts",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda coordinator: (
            window.start if (window := coordinator.next_prayer) else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IslamicPrayerTimesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Islamic prayer times sensor platform."""

    coordinator = config_entry.runtime_data
    async_add_entities(
        [
            *(
                IslamicPrayerTimeSensor(coordinator, description)
                for description in SENSOR_TYPES
            ),
            *(
                IslamicPrayerContextSensor(coordinator, description)
                for description in CONTEXT_SENSOR_TYPES
            ),
        ]
    )


class IslamicPrayerSensor(
    CoordinatorEntity[IslamicPrayerDataUpdateCoordinator], SensorEntity
):
    """Base for prayer sensors belonging to a location."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IslamicPrayerDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Islamic prayer time sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )


class IslamicPrayerTimeSensor(IslamicPrayerSensor):
    """Representation of an Islamic prayer time sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    @override
    def native_value(self) -> datetime:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]


class IslamicPrayerContextSensor(IslamicPrayerSensor):
    """Current or next prayer context from the shared calendar windows."""

    entity_description: IslamicPrayerContextSensorDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether a calculated window is available for this sensor."""
        return (
            super().available
            and self.coordinator.prayer_windows is not None
            and (
                not self.entity_description.requires_current
                or self.coordinator.current_prayer is not None
            )
        )

    @property
    @override
    def native_value(self) -> str | datetime | None:
        """Return the prayer name or boundary timestamp."""
        return self.entity_description.value_fn(self.coordinator)
