"""Sensors for the Beatbot integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from beatbot_cloud import (
    ERROR_BITS_BY_CATEGORY,
    STATUS_BY_CATEGORY,
    BeatbotDeviceData,
    ProductCategory,
    error_for,
    status_for,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity

_CATEGORY = ProductCategory.POOL_CLEAN_BOT
_STATUS_OPTIONS = list(
    dict.fromkeys(status.value for status in STATUS_BY_CATEGORY[_CATEGORY].values())
)
_ERROR_OPTIONS = [error.value for error, _ in ERROR_BITS_BY_CATEGORY[_CATEGORY]] + [
    "none"
]


def _status_value(data: BeatbotDeviceData) -> str | None:
    """Return the category-specific work status."""
    if status := status_for(ProductCategory(data.product_category), data.work_status):
        return status.value
    return None


def _error_value(data: BeatbotDeviceData) -> str:
    """Return the first active category-specific error."""
    if error := error_for(ProductCategory(data.product_category), data.error_code):
        return error.value
    return "none"


@dataclass(frozen=True, kw_only=True)
class BeatbotSensorEntityDescription(SensorEntityDescription):
    """Describe a Beatbot sensor entity."""

    value_fn: Callable[[BeatbotDeviceData], StateType]


SENSOR_DESCRIPTIONS: tuple[BeatbotSensorEntityDescription, ...] = (
    BeatbotSensorEntityDescription(
        key="status",
        translation_key="work_status",
        device_class=SensorDeviceClass.ENUM,
        options=_STATUS_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_status_value,
    ),
    BeatbotSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery_level,
    ),
    BeatbotSensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=SensorDeviceClass.ENUM,
        options=_ERROR_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_error_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        BeatbotSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSOR_DESCRIPTIONS
    )


class BeatbotSensor(BeatbotEntity, SensorEntity):
    """Represent a Beatbot sensor."""

    entity_description: BeatbotSensorEntityDescription

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
        description: BeatbotSensorEntityDescription,
    ) -> None:
        """Initialize a Beatbot sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.data)
