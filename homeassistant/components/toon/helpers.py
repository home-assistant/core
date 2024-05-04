"""Helpers for Toon."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from toonapi import ToonConnectionError, ToonError

from .models import ToonEntity

_ToonEntityT = TypeVar("_ToonEntityT", bound=ToonEntity)
_P = ParamSpec("_P")

_LOGGER = logging.getLogger(__name__)


def toon_exception_handler(
    func: Callable[Concatenate[_ToonEntityT, _P], Coroutine[Any, Any, None]],
) -> Callable[Concatenate[_ToonEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Toon calls to handle Toon exceptions.

    A decorator that wraps the passed in function, catches Toon errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self: _ToonEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except ToonConnectionError as error:
            _LOGGER.error("Error communicating with API: %s", error)
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()

        except ToonError as error:
            _LOGGER.error("Invalid response from API: %s", error)

    return handler
