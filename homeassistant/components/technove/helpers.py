"""Helpers for TechnoVE."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from technove import TechnoVEConnectionError, TechnoVEError

from homeassistant.exceptions import HomeAssistantError

from .entity import TechnoVEEntity

_TechnoVEEntityT = TypeVar("_TechnoVEEntityT", bound=TechnoVEEntity)
_P = ParamSpec("_P")


def technove_exception_handler(
    func: Callable[Concatenate[_TechnoVEEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_TechnoVEEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate TechnoVE calls to handle TechnoVE exceptions.

    A decorator that wraps the passed in function, catches TechnoVE errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(
        self: _TechnoVEEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)

        except TechnoVEConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError("Error communicating with TechnoVE API") from error

        except TechnoVEError as error:
            raise HomeAssistantError("Invalid response from TechnoVE API") from error

    return handler
