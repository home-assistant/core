"""Actions."""

from __future__ import annotations

import abc
from collections.abc import Callable, Coroutine, Mapping
import logging
from typing import Any, Protocol, override

from homeassistant.core import (
    EntityServiceResponse,
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)

from .integration_platform import async_process_integration_platforms
from .typing import VolSchemaType

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the action helper."""

    await async_process_integration_platforms(
        hass, "action", _register_action_platform, wait_for_platforms=True
    )


async def _register_action_platform(
    hass: HomeAssistant, integration_domain: str, platform: ActionProtocol
) -> None:
    """Register an action platform and notify listeners.

    If the action platform does not provide any actions, or it is disabled,
    listeners will not be notified.
    """

    if hasattr(platform, "async_get_actions"):
        if not (actions := await platform.async_get_actions(hass)):
            _LOGGER.debug(
                "Integration %s returned no actions in async_get_actions",
                integration_domain,
            )
            return
        for action_name, action_cls in actions.items():
            action_cls().async_register(hass, action_name)
    else:
        _LOGGER.debug(
            "Integration %s does not provide action support, skipping",
            integration_domain,
        )
        return


class Action(abc.ABC):
    """Action class."""

    @abc.abstractmethod
    def async_register(self, hass: HomeAssistant, name: str) -> None:
        """Register the action."""


class ActionProtocol(Protocol):
    """Define the format of action modules."""

    async def async_get_actions(self, hass: HomeAssistant) -> dict[str, type[Action]]:
        """Return the actions provided by this integration."""


def make_action(
    domain: str,
    *,
    description_placeholders: Mapping[str, str] | None = None,
    func: Callable[
        [ServiceCall],
        Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
        | ServiceResponse
        | EntityServiceResponse
        | None,
    ],
    job_type: HassJobType | None = None,
    schema: VolSchemaType | None = None,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> type[Action]:
    """Create an action definition."""

    class _Action(Action):
        """Define an action."""

        @override
        def async_register(self, hass: HomeAssistant, name: str) -> None:
            """Register the action."""
            hass.services.async_register(
                domain,
                service=name,
                service_func=func,
                job_type=job_type,
                schema=schema,
                supports_response=supports_response,
                description_placeholders=description_placeholders,
            )

    return _Action
