"""Generic entity code."""

from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from pyarcticspas import SpaResponse

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArcticSpaDataUpdateCoordinator
from .hottub import Device

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T", bound="CoordinatedEntity")
_P = ParamSpec("_P")


def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()

    return _async_wrap


class CoordinatedEntity(CoordinatorEntity[ArcticSpaDataUpdateCoordinator]):
    """Common base class for all coordinated Arctic Spa sensors."""

    _attr_has_entity_name = True

    @property
    def status(self) -> SpaResponse:
        """Expose a local Spa status so the remote endpoint is not overloaded."""
        return self._coordinator.status

    def __init__(
        self, device: Device, coordinator: ArcticSpaDataUpdateCoordinator
    ) -> None:
        """CoordinatedEntity is a base class for Arctic Spa sensors."""
        super().__init__(coordinator)
        self.device = device
        self._coordinator = coordinator
        self._attr_unique_id = self.device.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.id))},
            manufacturer="Arctic Spa",
            name="Arctic Spa",
        )
