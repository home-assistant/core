"""Base class for all SMLIGHT entities."""

from __future__ import annotations

from homeassistant.const import ATTR_CONNECTIONS, CONF_MAC
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import SmDataUpdateCoordinator


class SmEntity(CoordinatorEntity[SmDataUpdateCoordinator]):
    """Base class for all SMLight entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmDataUpdateCoordinator) -> None:
        """Initialize entity with device."""
        super().__init__(coordinator)

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.info.MAC)},
            configuration_url=f"http://{coordinator.client.host}",
            manufacturer=ATTR_MANUFACTURER,
            model=coordinator.data.info.model,
            name=coordinator.hostname,
            sw_version=f"core: {coordinator.data.info.sw_version} / zb: {coordinator.data.info.zb_version}",
        )

        if (mac := coordinator.config_entry.data.get(CONF_MAC)) is not None:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, format_mac(mac))
            }
