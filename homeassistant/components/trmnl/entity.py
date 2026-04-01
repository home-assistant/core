"""Base class for TRMNL entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from trmnl.exceptions import TRMNLError
from trmnl.models import Device

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TRMNLCoordinator


class TRMNLEntity(CoordinatorEntity[TRMNLCoordinator]):
    """Defines a base TRMNL entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TRMNLCoordinator, device_id: int) -> None:
        """Initialize TRMNL entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        device = self._device
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
            identifiers={(DOMAIN, str(device_id))},
            name=device.name,
            manufacturer="TRMNL",
        )

    @property
    def _device(self) -> Device:
        """Return the device from coordinator data."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self._device_id in self.coordinator.data


def exception_handler[_EntityT: TRMNLEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate TRMNL calls to handle exceptions.

    A decorator that wraps the passed in function, catches TRMNL errors.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except TRMNLError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
