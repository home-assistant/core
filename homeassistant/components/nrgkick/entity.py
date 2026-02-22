"""Base entity for NRGkick integration."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import async_api_call
from .const import DOMAIN
from .coordinator import NRGkickDataUpdateCoordinator


class NRGkickEntity(CoordinatorEntity[NRGkickDataUpdateCoordinator]):
    """Base class for NRGkick entities with common device info setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NRGkickDataUpdateCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key

        data = self.coordinator.data
        assert data is not None

        info_data: dict[str, Any] = data.info
        device_info: dict[str, Any] = info_data.get("general", {})
        network_info: dict[str, Any] = info_data.get("network", {})

        # The config flow requires a serial number and sets it as unique_id.
        serial = self.coordinator.config_entry.unique_id
        assert serial is not None

        # Get additional device info fields.
        versions: dict[str, Any] = info_data.get("versions", {})
        connections: set[tuple[str, str]] | None = None
        if (mac_address := network_info.get("mac_address")) and isinstance(
            mac_address, str
        ):
            connections = {(CONNECTION_NETWORK_MAC, mac_address)}

        self._attr_unique_id = f"{serial}_{self._key}"
        device_info_typed = DeviceInfo(
            configuration_url=f"http://{self.coordinator.config_entry.data[CONF_HOST]}",
            identifiers={(DOMAIN, serial)},
            serial_number=serial,
            manufacturer="DiniTech",
            model=device_info.get("model_type", "NRGkick Gen2"),
            sw_version=versions.get("sw_sm"),
            hw_version=versions.get("hw_sm"),
        )
        if connections is not None:
            device_info_typed["connections"] = connections

        self._attr_device_info = device_info_typed

    async def _async_call_api[_T](self, awaitable: Awaitable[_T]) -> _T:
        """Call the API, map errors, and refresh coordinator data."""
        result = await async_api_call(awaitable)
        await self.coordinator.async_refresh()
        return result
