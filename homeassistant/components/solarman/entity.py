"""Base entity for the Solarman integration."""

from __future__ import annotations

from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FW_VERSION, CONF_SN, DOMAIN
from .coordinator import SolarmanDeviceUpdateCoordinator


class SolarmanEntity(CoordinatorEntity[SolarmanDeviceUpdateCoordinator]):
    """Defines a Solarman entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarmanDeviceUpdateCoordinator) -> None:
        """Initialize the Solarman entity."""
        super().__init__(coordinator)

        entry = coordinator.config_entry

        sn = entry.data.get(CONF_SN, None)
        model = entry.data.get(CONF_MODEL, None)
        sw_version = entry.data.get(CONF_FW_VERSION, None)

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
