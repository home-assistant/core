"""Helpers for Hot Spring."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from hotspring import HotSpringConnectionError, HotSpringError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HotSpringEntity


def hotspring_exception_handler[_HotSpringEntityT: HotSpringEntity, **_P](
    func: Callable[Concatenate[_HotSpringEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_HotSpringEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Hot Spring calls to handle Hot Spring exceptions.

    A decorator that wraps the passed in function, catches Hot Spring errors,
    and raises a translated HomeAssistantError.
    """

    async def handler(
        self: _HotSpringEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except HotSpringConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from error
        except HotSpringError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from error

    return handler
