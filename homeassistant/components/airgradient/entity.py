"""Base class for AirGradient entities."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from airgradient import AirGradientConnectionError, AirGradientError, get_model_name

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirGradientCoordinator


class AirGradientEntity(CoordinatorEntity[AirGradientCoordinator]):
    """Defines a base AirGradient entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirGradientCoordinator) -> None:
        """Initialize airgradient entity."""
        super().__init__(coordinator)
        measures = coordinator.data.measures
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            manufacturer="AirGradient",
            model=get_model_name(measures.model),
            model_id=measures.model,
            serial_number=coordinator.serial_number,
            sw_version=measures.firmware_version,
        )


def exception_handler[_EntityT: AirGradientEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate AirGradient calls to handle exceptions.

    A decorator that wraps the passed in function, catches AirGradient errors.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except AirGradientConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

        except AirGradientError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
