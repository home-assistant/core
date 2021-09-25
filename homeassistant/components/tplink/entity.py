"""Common code for tplink."""
from __future__ import annotations

from typing import Any

from kasa import SmartDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TPLinkDataUpdateCoordinator


class CoordinatedTPLinkEntity(CoordinatorEntity):
    """Common base class for all coordinated tplink entities."""

    def __init__(
        self, device: SmartDevice, coordinator: TPLinkDataUpdateCoordinator
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device = device

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self.device.device_id

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Plug."""
        return self.device.alias

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "name": self.device.alias,
            "model": self.device.model,
            "manufacturer": "TP-Link",
            # Note: mac instead of device_id here to connect subdevices to the main device
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            "sw_version": self.device.hw_info["sw_ver"],
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.device.is_on
