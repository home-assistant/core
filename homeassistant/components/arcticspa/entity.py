"""Generic entity code."""

from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArcticSpaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T", bound="ArcticSpaEntity")
_P = ParamSpec("_P")


def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()

    return _async_wrap


class ArcticSpaEntity(CoordinatorEntity[ArcticSpaDataUpdateCoordinator]):
    """Common base class for all coordinated Arctic Spa sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArcticSpaDataUpdateCoordinator) -> None:
        """CoordinatedEntity is a base class for Arctic Spa sensors."""
        super().__init__(coordinator)

        self._attr_unique_id = coordinator.device.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device.id)},
            manufacturer="Arctic Spa",
            name="Hot Tub",
        )
