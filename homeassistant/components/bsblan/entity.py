"""BSBLan base entity."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BSBLanData
from .const import DOMAIN
from .coordinator import BSBLanFastCoordinator, BSBLanSlowCoordinator


class BSBLanEntity(CoordinatorEntity[BSBLanFastCoordinator]):
    """Defines a base BSBLan entity using the fast coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BSBLanFastCoordinator, data: BSBLanData) -> None:
        """Initialize BSBLan entity."""
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


class BSBLanSlowEntity(CoordinatorEntity[BSBLanSlowCoordinator]):
    """Defines a base BSBLan entity using the slow coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BSBLanSlowCoordinator, data: BSBLanData) -> None:
        """Initialize BSBLan entity."""
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


class BSBLanDualCoordinatorEntity(CoordinatorEntity[BSBLanFastCoordinator]):
    """Entity that listens to both fast and slow coordinators."""

    _attr_has_entity_name = True

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan entity with both coordinators."""
        super().__init__(fast_coordinator)
        self.slow_coordinator = slow_coordinator
        host = fast_coordinator.config_entry.data["host"]
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

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Also listen to slow coordinator updates
        self.async_on_remove(
            self.slow_coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from either coordinator."""
        self.async_write_ha_state()
