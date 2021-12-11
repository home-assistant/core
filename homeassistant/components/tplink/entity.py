"""Common code for tplink."""
from __future__ import annotations

from typing import Any, Callable, TypeVar, cast

from kasa import SmartDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])


def async_refresh_after(func: WrapFuncType) -> WrapFuncType:
    """Define a wrapper to refresh after."""

    async def _async_wrap(
        self: CoordinatedTPLinkEntity, *args: Any, **kwargs: Any
    ) -> None:
        await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh_without_children()

    return cast(WrapFuncType, _async_wrap)


class CoordinatedTPLinkEntity(CoordinatorEntity):
    """Common base class for all coordinated tplink entities."""

    coordinator: TPLinkDataUpdateCoordinator

    def __init__(
        self, device: SmartDevice, coordinator: TPLinkDataUpdateCoordinator
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device: SmartDevice = device
        self._attr_name = self.device.alias
        self._attr_unique_id = self.device.device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, str(self.device.device_id))},
            manufacturer="TP-Link",
            model=self.device.model,
            name=self.device.alias,
            sw_version=self.device.hw_info["sw_ver"],
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self.device.is_on)
