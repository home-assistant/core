"""Paperless-ngx base entity."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from homeassistant.components.sensor import EntityDescription
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import PaperlessConfigEntry
from .const import DOMAIN
from .coordinator import PaperlessRuntimeData


class PaperlessEntity(Entity):
    """Defines a base Paperless-ngx entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        data: PaperlessRuntimeData,
        entry: PaperlessConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize the Paperless-ngx entity."""
        self.data = data
        self.entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Paperless-ngx instance."""

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.entry.entry_id)},
            manufacturer="Paperless-ngx",
            name="Paperless-ngx",
            sw_version=self.data.client.host_version,
            configuration_url=self.data.client.base_url,
        )


TCoordinator = TypeVar("TCoordinator", bound=DataUpdateCoordinator[Any])


class PaperlessCoordinatorEntity(
    Generic[TCoordinator],
    CoordinatorEntity[TCoordinator],
    PaperlessEntity,
):
    """Defines a base Paperless-ngx coordinator entity."""

    def __init__(
        self,
        data: PaperlessRuntimeData,
        entry: PaperlessConfigEntry,
        description: EntityDescription,
        coordinator: TCoordinator,
    ) -> None:
        """Initialize the Paperless-ngx coordinator entity."""
        CoordinatorEntity.__init__(self, coordinator)
        PaperlessEntity.__init__(self, data, entry, description)
