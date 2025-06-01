"""Base entity for EHEIM Digital."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate

from eheimdigital.device import EheimDigitalDevice
from eheimdigital.types import EheimDigitalClientError

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EheimDigitalUpdateCoordinator


class EheimDigitalEntity[_DeviceT: EheimDigitalDevice](
    CoordinatorEntity[EheimDigitalUpdateCoordinator], ABC
):
    """Represent a EHEIM Digital entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EheimDigitalUpdateCoordinator, device: _DeviceT
    ) -> None:
        """Initialize a EHEIM Digital entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            # At this point at least one device is found and so there is always a main device set
            assert isinstance(coordinator.hub.main, EheimDigitalDevice)
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            name=device.name,
            connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
            manufacturer="EHEIM",
            model=device.device_type.model_name,
            identifiers={(DOMAIN, device.mac_address)},
            suggested_area=device.aquarium_name,
            sw_version=device.sw_version,
            via_device=(DOMAIN, coordinator.hub.main.mac_address),
        )
        self._device = device
        self._device_address = device.mac_address

    @abstractmethod
    def _async_update_attrs(self) -> None: ...

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()


def exception_handler[_EntityT: EheimDigitalEntity[EheimDigitalDevice], **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate AirGradient calls to handle exceptions.

    A decorator that wraps the passed in function, catches AirGradient errors.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except EheimDigitalClientError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
