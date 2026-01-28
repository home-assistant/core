"""Base entity for the Indevolt integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndevoltDeviceUpdateCoordinator


class IndevoltEntity(CoordinatorEntity[IndevoltDeviceUpdateCoordinator]):
    """Defines an Indevolt entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IndevoltDeviceUpdateCoordinator) -> None:
        """Initialize the Indevolt entity."""
        super().__init__(coordinator)

        entry = coordinator.config_entry
        if entry is not None:
            sn = entry.data.get("sn", "unknown")
            model = entry.data.get("model", "unknown")
            sw_version = entry.data.get("fw_version", "unknown")

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, sn)},
                name=f"Indevolt {model}",
                manufacturer="INDEVOLT",
                sw_version=sw_version,
                model=model,
                serial_number=sn,
            )
