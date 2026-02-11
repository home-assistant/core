"""Support for the Swedish weather institute weather  base entities."""

from __future__ import annotations

from abc import abstractmethod

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMHIDataUpdateCoordinator, SMHIFireDataUpdateCoordinator


class SmhiWeatherBaseEntity(Entity):
    """Representation of a base weather entity."""

    _attr_attribution = "Swedish weather institute (SMHI)"
    _attr_has_entity_name = True

    def __init__(
        self,
        latitude: str,
        longitude: str,
    ) -> None:
        """Initialize the SMHI base weather entity."""
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


class SmhiWeatherEntity(
    CoordinatorEntity[SMHIDataUpdateCoordinator], SmhiWeatherBaseEntity
):
    """Representation of a weather entity."""

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: SMHIDataUpdateCoordinator,
    ) -> None:
        """Initialize the SMHI base weather entity."""
        super().__init__(coordinator)
        SmhiWeatherBaseEntity.__init__(self, latitude, longitude)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_entity_data()
        super()._handle_coordinator_update()


class SmhiFireEntity(
    CoordinatorEntity[SMHIFireDataUpdateCoordinator], SmhiWeatherBaseEntity
):
    """Representation of a weather entity."""

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: SMHIFireDataUpdateCoordinator,
    ) -> None:
        """Initialize the SMHI base weather entity."""
        super().__init__(coordinator)
        SmhiWeatherBaseEntity.__init__(self, latitude, longitude)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_entity_data()
        super()._handle_coordinator_update()
