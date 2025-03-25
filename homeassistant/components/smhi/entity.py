"""Support for the Swedish weather institute weather  base entities."""

from __future__ import annotations

from abc import abstractmethod

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMHIDataUpdateCoordinator


class SmhiWeatherBaseEntity(CoordinatorEntity[SMHIDataUpdateCoordinator]):
    """Representation of a base weather entity."""

    _attr_attribution = "Swedish weather institute (SMHI)"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: SMHIDataUpdateCoordinator,
    ) -> None:
        """Initialize the SMHI base weather entity."""
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
