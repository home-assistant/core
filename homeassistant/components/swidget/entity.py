"""Common code for Swidget."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate, TypeVar

from swidget.swidgetdevice import SwidgetDevice
from typing_extensions import ParamSpec

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwidgetDataUpdateCoordinator

_T = TypeVar("_T", bound="CoordinatedSwidgetEntity")
_P = ParamSpec("_P")


def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        # await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    return _async_wrap


class CoordinatedSwidgetEntity(CoordinatorEntity[SwidgetDataUpdateCoordinator]):
    """Common base class for all coordinated entities."""

    def __init__(
        self, device: SwidgetDevice, coordinator: SwidgetDataUpdateCoordinator
    ) -> None:
        """Initialize the Swidget device."""
        super().__init__(coordinator)
        self.device: SwidgetDevice = device
        self._attr_name = self.device.friendly_name
        self._attr_unique_id = self.device.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac_address)},
            identifiers={(DOMAIN, str(self.device.id))},
            manufacturer="Swidget",
            model=self.device.model,
            name=self.device.friendly_name,
            sw_version=self.device.version,
        )
