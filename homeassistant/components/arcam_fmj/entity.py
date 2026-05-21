"""Base entity for Arcam FMJ integration."""

from collections.abc import Callable, Coroutine
import functools
from typing import Any

from arcam.fmj import ConnectionFailed

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArcamFmjCoordinator


def convert_exception[**_P, _R](
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Convert a connection failure into a translated HomeAssistantError."""

    @functools.wraps(func)
    async def _convert_exception(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except ConnectionFailed as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_failed"
            ) from exception

    return _convert_exception


class ArcamFmjEntity(CoordinatorEntity[ArcamFmjCoordinator]):
    """Base entity for Arcam FMJ."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_entity_registry_enabled_default = coordinator.state.zn == 1
        self._attr_unique_id = coordinator.zone_unique_id
        if description is not None:
            self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
            self.entity_description = description

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.client.connected
