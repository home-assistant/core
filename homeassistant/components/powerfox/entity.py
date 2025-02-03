"""Generic entity for Powerfox."""

from __future__ import annotations

from powerfox import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PowerfoxDataUpdateCoordinator


class PowerfoxEntity(CoordinatorEntity[PowerfoxDataUpdateCoordinator]):
    """Base entity for Powerfox."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PowerfoxDataUpdateCoordinator,
        device: Device,
    ) -> None:
        """Initialize Powerfox entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer="Powerfox",
            model=device.type.human_readable,
            name=device.name,
            serial_number=device.id,
        )
