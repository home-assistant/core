"""BSBLan base entity."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BSBLanData
from .const import DOMAIN
from .coordinator import BSBLanCoordinator, BSBLanFastCoordinator, BSBLanSlowCoordinator


class BSBLanEntityBase[T](CoordinatorEntity[Any]):
    """Base BSBLan entity with common device info setup."""

    _attr_has_entity_name = True

    def _setup_device_info(
        self, coordinator: BSBLanCoordinator, data: BSBLanData
    ) -> None:
        """Set up device info for the entity."""
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
        super().__init__(coordinator)
        self._setup_device_info(coordinator, data)


class BSBLanDualCoordinatorEntity(BSBLanEntityBase[BSBLanFastCoordinator]):
    """Entity that listens to both fast and slow coordinators."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan entity with both coordinators."""
        super().__init__(fast_coordinator)
        self.slow_coordinator = slow_coordinator
        self._setup_device_info(fast_coordinator, data)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Also listen to slow coordinator updates
        self.async_on_remove(
            self.slow_coordinator.async_add_listener(self._handle_coordinator_update)
        )
