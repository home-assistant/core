"""Sensors for the Beatbot integration."""

from typing import override

from beatbot_cloud import (
    ERROR_BITS_BY_CATEGORY,
    STATUS_BY_CATEGORY,
    ProductCategory,
    status_for,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity

_CATEGORY = ProductCategory.POOL_CLEAN_BOT
_STATUS_OPTIONS = list(
    dict.fromkeys(status.value for status in STATUS_BY_CATEGORY[_CATEGORY].values())
)
_ERROR_BITS = ERROR_BITS_BY_CATEGORY[_CATEGORY]
_ERROR_OPTIONS = [error.value for error, _ in _ERROR_BITS] + ["none"]


class BeatbotSensorEntity(BeatbotEntity, SensorEntity):
    """Base class for Beatbot sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def available(self) -> bool:
        """Return whether the device data is available."""
        return self.data.is_online and self.coordinator.last_update_success


class BeatbotStatusSensor(BeatbotSensorEntity):
    """Represent the pool cleaner status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _STATUS_OPTIONS
    _attr_translation_key = "work_status"

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_status"

    @property
    @override
    def native_value(self) -> str | None:
        """Return the decoded work status."""
        if status := status_for(_CATEGORY, self.data.work_status):
            return status.value
        return None


class BeatbotBatterySensor(BeatbotSensorEntity):
    """Represent the pool cleaner battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "battery"

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_battery"

    @property
    @override
    def native_value(self) -> int:
        """Return the battery percentage."""
        return self.data.battery_level


class BeatbotErrorSensor(BeatbotSensorEntity):
    """Represent the primary active pool cleaner error."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = _ERROR_OPTIONS
    _attr_translation_key = "error"

    def __init__(self, coordinator: BeatbotCoordinator, device_id: str) -> None:
        """Initialize the error sensor."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_error"

    @property
    @override
    def native_value(self) -> str:
        """Return the first active error."""
        for error, bit in _ERROR_BITS:
            if self.data.error_code & bit:
                return error.value
        return "none"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for device_id in coordinator.data
        for entity in (
            BeatbotStatusSensor(coordinator, device_id),
            BeatbotBatterySensor(coordinator, device_id),
            BeatbotErrorSensor(coordinator, device_id),
        )
    )
