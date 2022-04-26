"""Utilities for Plugwise."""
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

from plugwise.exceptions import PlugwiseException
from typing_extensions import Concatenate, ParamSpec

from homeassistant.exceptions import HomeAssistantError

from .entity import PlugwiseEntity

_P = ParamSpec("_P")
_R = TypeVar("_R")
_T = TypeVar("_T", bound=PlugwiseEntity)


def plugwise_command(
    func: Callable[Concatenate[_T, _P], Awaitable[_R]]  # type: ignore[misc]
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, _R]]:  # type: ignore[misc]
    """Decorate Plugwise calls that send commands/make changes to the device.

    A decorator that wraps the passed in function, catches Plugwise errors,
    and requests an coordinator update to update status of the devices asap.
    """

    async def handler(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except PlugwiseException as error:
            raise HomeAssistantError(
                f"Error communicating with API: {error}"
            ) from error
        finally:
            await self.coordinator.async_request_refresh()

    return handler
