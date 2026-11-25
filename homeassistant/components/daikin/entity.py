"""Base entity for Daikin."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiohttp import ClientError
from pydaikin.exceptions import DaikinException

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DaikinCoordinator


class DaikinEntity(CoordinatorEntity[DaikinCoordinator]):
    """Base entity for Daikin."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        info = self.device.values
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            manufacturer="Daikin",
            model=info.get("model"),
            name=info.get("name"),
            sw_version=info.get("ver", "").replace("_", "."),
        )


def daikin_exception_handler[_EntityT: DaikinEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Raise a Home Assistant error when a command to the device fails."""

    @wraps(func)
    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except (DaikinException, ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_communicating",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

    return handler
