"""Entities for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPDataUpdateCoordinator


class IPPEntity(CoordinatorEntity):
    """Defines a base IPP entity."""

    def __init__(
        self,
        *,
        entry_id: str,
        device_id: str,
        coordinator: IPPDataUpdateCoordinator,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the IPP entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._entry_id = entry_id
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this IPP device."""
        if self._device_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: self.coordinator.data.info.name,
            ATTR_MANUFACTURER: self.coordinator.data.info.manufacturer,
            ATTR_MODEL: self.coordinator.data.info.model,
            ATTR_SW_VERSION: self.coordinator.data.info.version,
        }
