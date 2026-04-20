"""Base entity for the Russound RNET integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, RNET_EXCEPTIONS
from .coordinator import RussoundRNETCoordinator


def command[_EntityT: RussoundRNETEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Wrap async calls to raise on request error."""

    @wraps(func)
    async def decorator(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except RNET_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={
                    "function_name": func.__name__,
                    "entity_id": self.entity_id,
                },
            ) from exc

    return decorator


class RussoundRNETEntity(CoordinatorEntity[RussoundRNETCoordinator]):
    """Base entity for Russound RNET."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RussoundRNETCoordinator,
        controller_id: int,
        zone_id: int,
        zone_name: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._controller_id = controller_id
        self._zone_id = zone_id
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{controller_id}_{zone_id}")},
            name=zone_name or f"Zone {zone_id}",
            manufacturer="Russound",
            model=entry.data.get("model"),
            via_device=(DOMAIN, entry.entry_id) if controller_id > 1 else None,
        )
