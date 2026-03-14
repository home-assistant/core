"""Sensor platform for the WebDAV integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiowebdav2 import QuotaInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WebDavConfigEntry, WebDavCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WebDavSensorEntityDescription(SensorEntityDescription):
    """Describes a WebDAV sensor entity."""

    value_fn: Callable[[QuotaInfo], int | None]
    available_fn: Callable[[QuotaInfo], bool]


SENSORS: tuple[WebDavSensorEntityDescription, ...] = (
    WebDavSensorEntityDescription(
        key="free_space",
        translation_key="free_space",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda quota: quota.available_bytes,
        available_fn=lambda quota: quota.available_bytes is not None,
    ),
    WebDavSensorEntityDescription(
        key="used_space",
        translation_key="used_space",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda quota: quota.used_bytes,
        available_fn=lambda quota: quota.used_bytes is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebDavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WebDAV sensors from a config entry."""
    # Only add sensors if the coordinator is available, which means that
    # the WebDAV server supports quota, and we were able to fetch the quota data.
    if (coordinator := entry.runtime_data.coordinator) is not None:
        async_add_entities(
            WebDavSensor(coordinator, description)
            for description in SENSORS
            if description.available_fn(coordinator.data)
        )


class WebDavSensor(CoordinatorEntity[WebDavCoordinator], SensorEntity):
    """Representation of a WebDAV sensor."""

    _attr_has_entity_name = True
    entity_description: WebDavSensorEntityDescription

    def __init__(
        self,
        coordinator: WebDavCoordinator,
        description: WebDavSensorEntityDescription,
    ) -> None:
        """Initialize the WebDAV sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
