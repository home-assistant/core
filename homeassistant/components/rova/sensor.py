"""Support for Rova garbage calendar."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RovaCoordinator

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=rova"}

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="gft",
        translation_key="bio",
    ),
    SensorEntityDescription(
        key="papier",
        translation_key="paper",
    ),
    SensorEntityDescription(
        key="pmd",
        translation_key="plastic",
    ),
    SensorEntityDescription(
        key="restafval",
        translation_key="residual",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Rova entry."""
    coordinator: RovaCoordinator = hass.data[DOMAIN][entry.entry_id]

    assert entry.unique_id
    unique_id = entry.unique_id

    async_add_entities(
        RovaSensor(unique_id, description, coordinator) for description in SENSOR_TYPES
    )


class RovaSensor(CoordinatorEntity[RovaCoordinator], SensorEntity):
    """Representation of a Rova sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        description: SensorEntityDescription,
        coordinator: RovaCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
