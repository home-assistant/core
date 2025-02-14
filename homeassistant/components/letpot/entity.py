"""Base class for LetPot entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Concatenate

from letpot.exceptions import LetPotConnectionException, LetPotException

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LetPotDeviceCoordinator


@dataclass(frozen=True, kw_only=True)
class LetPotEntityDescription(EntityDescription):
    """Description for all LetPot entities."""

    supported_fn: Callable[[LetPotDeviceCoordinator], bool] = lambda _: True


class LetPotEntity(CoordinatorEntity[LetPotDeviceCoordinator]):
    """Defines a base LetPot entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LetPotDeviceCoordinator) -> None:
        """Initialize a LetPot entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device.serial_number)},
            name=coordinator.device.name,
            manufacturer="LetPot",
            model=coordinator.device_client.device_model_name,
            model_id=coordinator.device_client.device_model_code,
            serial_number=coordinator.device.serial_number,
        )


def exception_handler[_EntityT: LetPotEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate the function to catch LetPot exceptions and raise them correctly."""

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except LetPotConnectionException as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"exception": str(exception)},
            ) from exception
        except LetPotException as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"exception": str(exception)},
            ) from exception

    return handler
