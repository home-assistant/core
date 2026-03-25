"""Tessie helper functions."""

import logging
from typing import Any

from aiohttp import ClientError
from tesla_fleet_api.exceptions import TeslaFleetError
from tesla_fleet_api.tessie import Tessie

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, TRANSLATED_ERRORS

_LOGGER = logging.getLogger(__name__)


async def fetch_state_of_all_vehicles(
    api: Tessie, only_active: bool = True
) -> dict[str, Any]:
    """Fetch the latest state for all vehicles."""
    return await api.list_vehicles(only_active=only_active)


async def handle_command(command, name: str | None = None) -> dict[str, Any]:
    """Handle a command."""
    try:
        result = await command
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from e
    except TeslaFleetError as e:
        key = getattr(e, "key", None)
        error_key: str = key if isinstance(key, str) else "unknown"
        translation_key = TRANSLATED_ERRORS.get(error_key, "command_failed")
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"message": e.message, "name": name or "Entity"},
        ) from e

    response = result.get("response", result)
    if response.get("result") is False:
        reason = response.get("reason", "unknown")
        translation_key = TRANSLATED_ERRORS.get(reason, "command_failed")
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"message": reason, "name": name or "Entity"},
        )

    _LOGGER.debug("Command result: %s", result)
    return result
