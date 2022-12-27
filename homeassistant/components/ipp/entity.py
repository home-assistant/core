"""Entities for The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IPPDataUpdateCoordinator


class IPPEntity(CoordinatorEntity[IPPDataUpdateCoordinator]):
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
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this IPP device."""
        if self._device_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=self.coordinator.data.info.manufacturer,
            model=self.coordinator.data.info.model,
            name=self.coordinator.data.info.name,
            sw_version=self.coordinator.data.info.version,
            configuration_url=self.coordinator.data.info.more_info,
        )
