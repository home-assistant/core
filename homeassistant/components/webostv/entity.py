"""Base entity for the LG webOS TV integration."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aiowebostv import WebOsTvCommandError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WebOsTvConfigEntry, WebOsTvDataUpdateCoordinator


class WebOsTvEntity(CoordinatorEntity[WebOsTvDataUpdateCoordinator]):
    """Base entity for the LG webOS TV integration."""

    _attr_has_entity_name = True

    def __init__(self, entry: WebOsTvConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data)
        self._client = entry.runtime_data.client
        self._attr_device_info = entry.runtime_data.device_info


def cmd[_EntityT: WebOsTvEntity, _R, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, _R]]:
    """Catch command exceptions."""

    @wraps(func)
    async def cmd_wrapper(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Wrap all command methods."""
        if not self._client.tv_state.is_on and func.__name__ != "async_turn_off":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_off",
                translation_placeholders={
                    "name": self.coordinator.name,
                    "func": func.__name__,
                },
            )
        try:
            return await func(self, *args, **kwargs)
        except WebOsTvCommandError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "name": self.coordinator.name,
                    "func": func.__name__,
                    "error": str(error),
                },
            ) from error

    return cmd_wrapper
