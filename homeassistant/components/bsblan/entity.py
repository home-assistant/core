"""BSBLan base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BSBLanData
from .const import DOMAIN
from .coordinator import BSBLanCoordinator, BSBLanFastCoordinator, BSBLanSlowCoordinator


class BSBLanEntityBase[_T: BSBLanCoordinator](CoordinatorEntity[_T]):
    """Base BSBLan entity with common device info setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _T, data: BSBLanData) -> None:
        """Initialize BSBLan entity with device info."""
        super().__init__(coordinator)
        host = coordinator.config_entry.data["host"]
        mac = data.device.MAC
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, format_mac(mac))},
            name=data.device.name,
            manufacturer="BSBLAN Inc.",
            model=data.info.device_identification.value,
            sw_version=data.device.version,
            configuration_url=f"http://{host}",
        )


class BSBLanEntity(BSBLanEntityBase[BSBLanFastCoordinator]):
    """Defines a base BSBLan entity using the fast coordinator."""

    def __init__(self, coordinator: BSBLanFastCoordinator, data: BSBLanData) -> None:
        """Initialize BSBLan entity."""
        super().__init__(coordinator, data)


class BSBLanDualCoordinatorEntity(BSBLanEntity):
    """Entity that listens to both fast and slow coordinators."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan entity with both coordinators."""
        super().__init__(fast_coordinator, data)
        self.slow_coordinator = slow_coordinator

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Also listen to slow coordinator updates
        self.async_on_remove(
            self.slow_coordinator.async_add_listener(self._handle_coordinator_update)
        )
