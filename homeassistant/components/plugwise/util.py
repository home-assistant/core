"""Utilities for Plugwise."""
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from plugwise.exceptions import PlugwiseException

from homeassistant.exceptions import HomeAssistantError

from .entity import PlugwiseEntity

_PlugwiseEntityT = TypeVar("_PlugwiseEntityT", bound=PlugwiseEntity)
_R = TypeVar("_R")
_P = ParamSpec("_P")


def plugwise_command(
    func: Callable[Concatenate[_PlugwiseEntityT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_PlugwiseEntityT, _P], Coroutine[Any, Any, _R]]:
    """Decorate Plugwise calls that send commands/make changes to the device.

    A decorator that wraps the passed in function, catches Plugwise errors,
    and requests an coordinator update to update status of the devices asap.
    """

    async def handler(
        self: _PlugwiseEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except PlugwiseException as error:
            raise HomeAssistantError(
                f"Error communicating with API: {error}"
            ) from error
        finally:
            await self.coordinator.async_request_refresh()

    return handler
