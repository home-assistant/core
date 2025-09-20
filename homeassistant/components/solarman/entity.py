"""Base entity for the Solarman integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarmanDeviceUpdateCoordinator


class SolarmanEntity(CoordinatorEntity[SolarmanDeviceUpdateCoordinator]):
    """Defines a Solarman entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarmanDeviceUpdateCoordinator) -> None:
        """Initialize the Solarman entity."""
        super().__init__(coordinator)

        entry = coordinator.config_entry
        if entry is not None:
            sn = entry.data.get("sn", "unknown")
            model = entry.data.get("model", "unknown")
            sw_version = entry.data.get("fw_version", "unknown")

            name = ""
            if model == "SP-2W-EU":
                name = "Smart Plug"
            elif model == "P1-2W":
                name = "P1 Meter Reader"
            elif model == "gl meter":
                name = "Smart Meter"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, sn)},
                name=name,
                manufacturer="SOLARMAN",
                sw_version=sw_version,
                model=model,
                serial_number=sn,
            )
