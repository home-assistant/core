"""Handle KNX Devices."""

from __future__ import annotations

from xknx import XKNX
from xknx.core import XknxConnectionState
from xknx.io.gateway_scanner import GatewayDescriptor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class KNXInterfaceDevice:
    """Class for KNX Interface Device handling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, xknx: XKNX) -> None:
        """Initialize interface device class."""
        self.hass = hass
        self.device_registry = dr.async_get(hass)
        self.gateway_descriptor: GatewayDescriptor | None = None
        self.xknx = xknx

        _device_id = (DOMAIN, f"_{entry.entry_id}_interface")
        self.device = self.device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            name="KNX Interface",
            identifiers={_device_id},
        )
        self.device_info = DeviceInfo(identifiers={_device_id})

        self.xknx.connection_manager.register_connection_state_changed_cb(
            self.connection_state_changed_cb
        )

    async def update(self) -> None:
        """Update interface properties on new connection."""
        self.gateway_descriptor = await self.xknx.knxip_interface.gateway_info()

        self.device_registry.async_update_device(
            device_id=self.device.id,
            model=str(self.gateway_descriptor.name)
            if self.gateway_descriptor
            else None,
        )

    def connection_state_changed_cb(self, state: XknxConnectionState) -> None:
        """Call invoked after a KNX connection state change was received."""
        if state is XknxConnectionState.CONNECTED:
            self.hass.async_create_task(self.update())
