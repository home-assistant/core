"""Base entity for the Cyclus NV integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BAG_ID, DOMAIN
from .coordinator import CyclusNVConfigEntry, CyclusNVDataUpdateCoordinator


class CyclusNVEntity(CoordinatorEntity[CyclusNVDataUpdateCoordinator]):
    """Defines a Cyclus NV entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: CyclusNVConfigEntry) -> None:
        """Initialize the Cyclus NV entity."""
        super().__init__(coordinator=entry.runtime_data)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.cyclusnv.nl",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.data[CONF_BAG_ID])},
            manufacturer="Cyclus NV",
        )
