"""Support for the Swedish weather institute weather  base entities."""

from abc import abstractmethod
from typing import Any, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class SmhiEntity[_DataUpdateCoordinatorT: DataUpdateCoordinator[Any]](
    CoordinatorEntity[_DataUpdateCoordinatorT]
):
    """Representation of a SMHI entity."""

    _attr_attribution = "Swedish weather institute (SMHI)"
    _attr_has_entity_name = True

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: _DataUpdateCoordinatorT,
    ) -> None:
        """Initialize the SMHI entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{latitude}, {longitude}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{latitude}, {longitude}")},
            manufacturer="SMHI",
            model="v2",
            configuration_url="http://opendata.smhi.se/apidocs/metfcst/parameters.html",
        )
        self.update_entity_data()

    @abstractmethod
    def update_entity_data(self) -> None:
        """Refresh the entity data."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_entity_data()
        super()._handle_coordinator_update()
