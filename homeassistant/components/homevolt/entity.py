"""Shared entity helpers for Homevolt."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from homevolt import (
    HomevoltAuthenticationError,
    HomevoltCommandOutcomeUnknownError,
    HomevoltCommandRejectedError,
    HomevoltCommandVerificationError,
    HomevoltConnectionError,
    HomevoltError,
)

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HomevoltDataUpdateCoordinator


class HomevoltEntity(CoordinatorEntity[HomevoltDataUpdateCoordinator]):
    """Base Homevolt entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HomevoltDataUpdateCoordinator, device_identifier: str
    ) -> None:
        """Initialize the Homevolt entity."""
        super().__init__(coordinator)
        device_id = coordinator.data.unique_id
        device_metadata = coordinator.data.device_metadata.get(device_identifier)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_id}_{device_identifier}")},
            configuration_url=coordinator.client.base_url,
            manufacturer=MANUFACTURER,
            model=device_metadata.model if device_metadata else None,
            name=device_metadata.name if device_metadata else None,
        )


def homevolt_exception_handler[_HomevoltEntityT: HomevoltEntity, **_P](
    func: Callable[Concatenate[_HomevoltEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_HomevoltEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Homevolt calls to handle exceptions."""

    async def handler(
        self: _HomevoltEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except HomevoltAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from error
        except HomevoltCommandRejectedError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(error)},
            ) from error
        except HomevoltCommandVerificationError as error:
            await self.coordinator.async_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_verification_failed",
                translation_placeholders={"error": str(error)},
            ) from error
        except HomevoltCommandOutcomeUnknownError as error:
            await self.coordinator.async_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_outcome_unknown",
                translation_placeholders={"error": str(error)},
            ) from error
        except HomevoltConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error
        except HomevoltError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
