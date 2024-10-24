"""Support for the Swiss Public Transport times."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    SwissPublicTransportConfigEntry,
    SwissPublicTransportDataUpdateCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwissPublicTransportConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add connection config departure time from a config_entry."""
    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    async_add_entities(
        [SwissPublicTransportDepartureTime(config_entry.runtime_data, unique_id)]
    )


class SwissPublicTransportDepartureTime(
    CoordinatorEntity[SwissPublicTransportDataUpdateCoordinator], TimeEntity
):
    """Define a depature time."""

    entity_description: TimeEntityDescription
    _attr_attribution = "Data provided by transport.opendata.ch"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SwissPublicTransportDataUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize the time."""
        super().__init__(coordinator)
        self.entity_description = TimeEntityDescription(
            key="departure_time",
            translation_key="departure_time",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_unique_id = f"{unique_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Opendata.ch",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> time:
        """Return the departure time."""
        return self.coordinator.departure_time

    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        self.coordinator.departure_time = value
        await self.coordinator.save_store()
