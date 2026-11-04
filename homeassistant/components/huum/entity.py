"""Define Huum Base entity."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from huum.exceptions import HuumError, SafetyException

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HuumDataUpdateCoordinator


class HuumBaseEntity(CoordinatorEntity[HuumDataUpdateCoordinator]):
    """Huum base Entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Huum sauna",
            manufacturer="Huum",
            model="UKU WiFi",
        )


def huum_exception_handler[_EntityT: HuumBaseEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Huum actions to raise translated errors."""

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except SafetyException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_turn_on",
            ) from err
        except HuumError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

    return handler
