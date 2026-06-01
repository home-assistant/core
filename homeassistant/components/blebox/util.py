"""Utilities for BleBox."""

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate

from blebox_uniapi.error import Error

from homeassistant.exceptions import HomeAssistantError

from .entity import BleBoxEntity


def blebox_command[_BleBoxEntityT: BleBoxEntity, **_P, _R](
    func: Callable[Concatenate[_BleBoxEntityT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_BleBoxEntityT, _P], Coroutine[Any, Any, _R]]:
    """Decorate BleBox calls that send commands to the device.

    Catches BleBox errors and refreshes the coordinator after the command.
    """

    async def handler(self: _BleBoxEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except Error as err:
            raise HomeAssistantError(str(err)) from err
        finally:
            await self.coordinator.async_refresh()

    return handler
