"""Common code for tplink."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from kasa import SmartDevice, SmartDeviceException

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator

_T = TypeVar("_T", bound="CoordinatedTPLinkEntity")
_P = ParamSpec("_P")


def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to catch exceptions and refresh after calls."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except SmartDeviceException as ex:
            raise HomeAssistantError("Unable to communicate with the device") from ex

        await self.coordinator.async_request_refresh()

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
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, str(device.device_id))},
            manufacturer="TP-Link",
            model=device.model,
            name=device.alias,
            sw_version=device.hw_info["sw_ver"],
            hw_version=device.hw_info["hw_ver"],
        )
