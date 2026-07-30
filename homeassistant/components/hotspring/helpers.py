"""Helpers for Hot Spring."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from hotspring import HotSpringConnectionError, HotSpringError

from homeassistant.exceptions import HomeAssistantError

from .entity import HotSpringEntity


def hotspring_exception_handler[_HotSpringEntityT: HotSpringEntity, **_P](
    func: Callable[Concatenate[_HotSpringEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_HotSpringEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Hot Spring calls to handle Hot Spring exceptions."""

    async def handler(
        self: _HotSpringEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)

        except HotSpringConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError("Error communicating with Hot Spring API") from error

        except HotSpringError as error:
            raise HomeAssistantError("Invalid response from Hot Spring API") from error

    return handler

