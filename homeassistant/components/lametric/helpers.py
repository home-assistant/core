"""Helpers for LaMetric."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from demetriek import LaMetricConnectionError, LaMetricError
from typing_extensions import Concatenate, ParamSpec

from homeassistant.exceptions import HomeAssistantError

from .entity import LaMetricEntity

_LaMetricEntityT = TypeVar("_LaMetricEntityT", bound=LaMetricEntity)
_P = ParamSpec("_P")


def lametric_exception_handler(
    func: Callable[Concatenate[_LaMetricEntityT, _P], Coroutine[Any, Any, Any]]
) -> Callable[Concatenate[_LaMetricEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate LaMetric calls to handle LaMetric exceptions.

    A decorator that wraps the passed in function, catches LaMetric errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(
        self: _LaMetricEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except LaMetricConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                "Error communicating with the LaMetric device"
            ) from error

        except LaMetricError as error:
            raise HomeAssistantError(
                "Invalid response from the LaMetric device"
            ) from error

    return handler
