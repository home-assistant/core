"""Support for the Swiss Public Transport times."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
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
    """Add connection config departure time offset from a config_entry."""
    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    async_add_entities(
        [SwissPublicTransportDepartureTimeOffset(config_entry.runtime_data, unique_id)]
    )


class SwissPublicTransportDepartureTimeOffset(
    CoordinatorEntity[SwissPublicTransportDataUpdateCoordinator], NumberEntity
):
    """Define a depature time offset."""

    entity_description: NumberEntityDescription
    _attr_attribution = "Data provided by transport.opendata.ch"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SwissPublicTransportDataUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = NumberEntityDescription(
            key="departure_time_offset",
            translation_key="departure_time_offset",
            entity_category=EntityCategory.CONFIG,
            native_min_value=0,
            native_step=1,
            mode=NumberMode.BOX,
        )
        self._attr_unique_id = f"{unique_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Opendata.ch",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float:
        """Return the departure time offset."""
        return self.coordinator.departure_time_offset.total_seconds() / 60

    async def async_set_native_value(self, value: float) -> None:
        """Change the time offset."""
        self.coordinator.departure_time_offset = timedelta(minutes=value)
        await self.coordinator.save_store()
