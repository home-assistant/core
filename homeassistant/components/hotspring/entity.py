"""Entity for Hot Spring."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from hotspring import HotSpringConnectionError, HotSpringError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HotSpringDataUpdateCoordinator

_P = ParamSpec("_P")
_R = TypeVar("_R")


def exception_handler(
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Decorate Hot Spring API calls to catch and translate exceptions."""

    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except HotSpringConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(error)},
            ) from error
        except HotSpringError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
                translation_placeholders={"error": str(error)},
            ) from error

    return wrapper


class HotSpringEntity(CoordinatorEntity[HotSpringDataUpdateCoordinator]):
    """Defines a base Hot Spring entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HotSpringDataUpdateCoordinator, key: str) -> None:
        """Initialize a base Hot Spring entity."""
        super().__init__(coordinator)
        info = self.coordinator.data.info
        self._attr_unique_id = f"{info.mac_address}_{key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, info.mac_address)},
            identifiers={(DOMAIN, info.mac_address)},
            name=info.hostname or "Hot Spring Spa",
            manufacturer="Hot Spring",
            model=info.model or "Connected Spa",
        )
