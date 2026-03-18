"""Base entity for the Solarman integration."""

from __future__ import annotations

from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SN, DOMAIN, MODEL_NAME_MAP
from .coordinator import SolarmanDeviceUpdateCoordinator


class SolarmanEntity(CoordinatorEntity[SolarmanDeviceUpdateCoordinator]):
    """Defines a Solarman entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarmanDeviceUpdateCoordinator) -> None:
        """Initialize the Solarman entity."""
        super().__init__(coordinator)

        entry = coordinator.config_entry

        sn = entry.data[CONF_SN]
        model_id = entry.data[CONF_MODEL]

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, entry.data[CONF_MAC])},
            identifiers={(DOMAIN, sn)},
            manufacturer="SOLARMAN",
            model=MODEL_NAME_MAP[model_id],
            model_id=model_id,
            serial_number=sn,
        )
