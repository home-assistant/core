"""Utility functions for the Portainer integration."""

from collections.abc import Coroutine
from typing import Any

from pyportainer import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def sanitize_container_name(container_name: str) -> str:
    """Sanitize to get a proper container name."""
    return container_name.replace("/", " ").strip()


async def async_call_portainer(coroutine: Coroutine[Any, Any, Any]) -> None:
    """Await a Portainer call, mapping library errors to HomeAssistantError."""
    try:
        await coroutine
    except PortainerAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except PortainerConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except PortainerTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
        ) from err
