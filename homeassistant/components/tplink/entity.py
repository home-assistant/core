"""Common code for tplink."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from kasa import SmartDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator

_T = TypeVar("_T", bound="CoordinatedTPLinkEntity")
_P = ParamSpec("_P")


def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh_without_children()

    return _async_wrap


class CoordinatedTPLinkEntity(CoordinatorEntity[TPLinkDataUpdateCoordinator]):
    """Common base class for all coordinated tplink entities."""

    _attr_has_entity_name = True

    def __init__(
        self, device: SmartDevice, coordinator: TPLinkDataUpdateCoordinator
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device: SmartDevice = device
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
            hw_version=self.device.hw_info["hw_ver"],
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return bool(self.device.is_on)
