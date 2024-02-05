"""Helpers for HomeWizard."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, ParamSpec, TypeVar

from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import HomeWizardEntity

_HomeWizardEntityT = TypeVar("_HomeWizardEntityT", bound=HomeWizardEntity)
_P = ParamSpec("_P")


def homewizard_exception_handler(
    func: Callable[Concatenate[_HomeWizardEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_HomeWizardEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate HomeWizard Energy calls to handle HomeWizardEnergy exceptions.

    A decorator that wraps the passed in function, catches HomeWizardEnergy errors,
    and reloads the integration when the API was disabled so the reauth flow is
    triggered.
    """

    async def handler(
        self: _HomeWizardEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except RequestError as ex:
            raise HomeAssistantError(
                "An error occurred while communicating with HomeWizard device",
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from ex
        except DisabledError as ex:
            await self.hass.config_entries.async_reload(
                self.coordinator.config_entry.entry_id
            )
            raise HomeAssistantError(
                "The local API of the HomeWizard device is disabled",
                translation_domain=DOMAIN,
                translation_key="api_disabled",
            ) from ex

    return handler
