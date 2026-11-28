"""Shared Home Assistant entity behavior for Zentraly."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, override

from zentraly import (
    ZentralyApiError,
    ZentralyCommandRejectedError,
    ZentralyConnectionBusyError,
    ZentralyConnectionError,
    ZentralyInvalidResponseError,
    ZentralyValidationError,
)

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZentralyUpdateCoordinator


def translate_action_errors[**P, R](
    action: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Convert protocol errors without exposing technical details to the UI."""

    @wraps(action)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await action(*args, **kwargs)
        except ZentralyValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_action"
            ) from err
        except ZentralyApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=_error_key(err)
            ) from err

    return wrapped


def _error_key(error: ZentralyApiError) -> str:
    """Map library failures to integration translation keys."""
    for error_type, key in (
        (ZentralyConnectionBusyError, "connection_busy"),
        (ZentralyConnectionError, "cannot_connect"),
        (ZentralyInvalidResponseError, "invalid_response"),
        (ZentralyCommandRejectedError, "command_rejected"),
    ):
        if isinstance(error, error_type):
            return key
    return "action_failed"


class ZentralyEntity(CoordinatorEntity[ZentralyUpdateCoordinator]):
    """Represent one capability of a directly connected or child device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZentralyUpdateCoordinator) -> None:
        """Attach the represented device and its refresh coordinator."""
        super().__init__(coordinator)
        self._device = coordinator.device

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the represented physical device's registry information."""
        return self._device.device_info

    @property
    @override
    def available(self) -> bool:
        """Keep device availability independent of a missing individual reading."""
        return super().available and self._device.available and self._device.connected

    @override
    async def async_update(self) -> None:
        """Request an explicit refresh without the periodic polling preference."""
        await self.coordinator.async_refresh()
