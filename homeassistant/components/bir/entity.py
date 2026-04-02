"""Base entity for the BIR integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PROPERTY_ID, DOMAIN
from .coordinator import BirConfigEntry, BirDataUpdateCoordinator


class BirEntity(CoordinatorEntity[BirDataUpdateCoordinator]):
    """Define a base BIR entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: BirConfigEntry) -> None:
        """Initialize the BIR entity."""
        super().__init__(coordinator=entry.runtime_data)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://bir.no",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.data[CONF_PROPERTY_ID])},
            manufacturer="BIR",
            name=entry.runtime_data.address,
        )
