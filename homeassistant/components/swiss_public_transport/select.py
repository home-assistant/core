"""Support for the Swiss Public Transport selects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEPARTURE_MODE_OPTIONS, DOMAIN
from .coordinator import (
    SwissPublicTransportConfigEntry,
    SwissPublicTransportDataUpdateCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwissPublicTransportConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add connection config select from a config_entry."""
    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    async_add_entities(
        [SwissPublicTransportDepartureModeSelect(config_entry.runtime_data, unique_id)]
    )


class SwissPublicTransportDepartureModeSelect(
    CoordinatorEntity[SwissPublicTransportDataUpdateCoordinator], SelectEntity
):
    """Define a depature mode select."""

    entity_description: SelectEntityDescription
    _attr_attribution = "Data provided by transport.opendata.ch"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SwissPublicTransportDataUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_description = SelectEntityDescription(
            key="departure_mode",
            translation_key="departure_mode",
            entity_category=EntityCategory.CONFIG,
            options=DEPARTURE_MODE_OPTIONS,
        )
        self._attr_unique_id = f"{unique_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Opendata.ch",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_current_option = self.coordinator.departure_mode

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    def _get_current_option(self) -> str:
        return self.coordinator.departure_mode

    @callback
    def _async_update_attrs(self) -> None:
        """Update select attributes."""
        self._attr_current_option = self._get_current_option()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.coordinator.departure_mode = option
        await self.coordinator.save_store()
