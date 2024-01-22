"""Fully Kiosk Browser sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


def round_storage(value: int) -> float:
    """Convert storage values from bytes to megabytes."""
    return round(value * 0.000001, 1)


def truncate_url(value: StateType) -> tuple[StateType, dict[str, Any]]:
    """Truncate URL if longer than 256."""
    url = str(value)
    truncated = len(url) > 256
    extra_state_attributes = {
        "full_url": url,
        "truncated": truncated,
    }
    if truncated:
        return (url[0:255], extra_state_attributes)
    return (url, extra_state_attributes)


@dataclass(frozen=True)
class FullySensorEntityDescription(SensorEntityDescription):
    """Fully Kiosk Browser sensor description."""

    round_state_value: bool = False
    state_fn: Callable[[StateType], tuple[StateType, dict[str, Any]]] | None = None


SENSORS: tuple[FullySensorEntityDescription, ...] = (
    FullySensorEntityDescription(
        key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="currentPage",
        translation_key="current_page",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_fn=truncate_url,
    ),
    FullySensorEntityDescription(
        key="screenOrientation",
        translation_key="screen_orientation",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="foregroundApp",
        translation_key="foreground_app",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FullySensorEntityDescription(
        key="internalStorageFreeSpace",
        translation_key="internal_storage_free_space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        round_state_value=True,
    ),
    FullySensorEntityDescription(
        key="internalStorageTotalSpace",
        translation_key="internal_storage_total_space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        round_state_value=True,
    ),
    FullySensorEntityDescription(
        key="ramFreeMemory",
        translation_key="ram_free_memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        round_state_value=True,
    ),
    FullySensorEntityDescription(
        key="ramTotalMemory",
        translation_key="ram_total_memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        round_state_value=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser sensor."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        FullySensor(coordinator, description)
        for description in SENSORS
        if description.key in coordinator.data
    )


class FullySensor(FullyKioskEntity, SensorEntity):
    """Representation of a Fully Kiosk Browser sensor."""

    entity_description: FullySensorEntityDescription

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        sensor: FullySensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        self.entity_description = sensor

        self._attr_unique_id = f"{coordinator.data['deviceID']}-{sensor.key}"

        super().__init__(coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        extra_state_attributes: dict[str, Any] = {}
        value = self.coordinator.data.get(self.entity_description.key)

        if value is not None:
            if self.entity_description.state_fn is not None:
                value, extra_state_attributes = self.entity_description.state_fn(value)

            if self.entity_description.round_state_value:
                value = round_storage(value)

        self._attr_native_value = value
        self._attr_extra_state_attributes = extra_state_attributes

        self.async_write_ha_state()
