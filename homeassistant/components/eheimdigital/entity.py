"""Base entity for EHEIM Digital."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Concatenate, override

from eheimdigital.device import EheimDigitalDevice
from eheimdigital.types import EheimDigitalClientError

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EheimDigitalUpdateCoordinator


def async_device_info(
    coordinator: EheimDigitalUpdateCoordinator, device: EheimDigitalDevice
) -> DeviceInfo:
    """Return the base device info for an EHEIM Digital device."""
    return DeviceInfo(
        configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
        name=device.name,
        connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
        manufacturer="EHEIM",
        model=device.model_name,
        identifiers={(DOMAIN, device.mac_address)},
        suggested_area=device.aquarium_name,
        sw_version=device.sw_version,
    )


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
        main = coordinator.hub.main
        if TYPE_CHECKING:
            # At this point at least one device is found
            # and so there is always a main device set
            assert isinstance(main, EheimDigitalDevice)
        self._attr_device_info = async_device_info(coordinator, device)
        if device.mac_address != main.mac_address:
            # The main device is registered during setup, before the platforms
            # are forwarded, so this link always resolves deterministically.
            self._attr_device_info["via_device_id"] = (
                dr.async_get_device_id_by_identifier(
                    coordinator.hass,
                    (DOMAIN, main.mac_address),
                    config_entry_id=coordinator.config_entry.entry_id,
                )
            )
        self._device = device
        self._device_address = device.mac_address

    @abstractmethod
    def _async_update_attrs(self) -> None: ...

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()


def exception_handler[_EntityT: EheimDigitalEntity[EheimDigitalDevice], **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate eheimdigital calls to handle exceptions.

    A decorator that wraps the passed in function, catches eheimdigital errors.
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
