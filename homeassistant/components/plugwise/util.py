"""Utilities for Plugwise."""

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate

from packaging import version
from plugwise.exceptions import PlugwiseException

from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_TIMEOUT
from .entity import PlugwiseEntity


def get_timeout_for_version(version_str: str) -> int:
    """Determine timeout value based on gateway version.

    A gateway firmware version > 3.2.0 should mean a latest-generation-device, allowing for a timeout of 10s.
    Legacy devices require a timeout of 30s.
    """
    if version.parse(version_str) >= version.parse("3.2.0"):
        return 10
    return DEFAULT_TIMEOUT


def plugwise_command[_PlugwiseEntityT: PlugwiseEntity, **_P, _R](
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
