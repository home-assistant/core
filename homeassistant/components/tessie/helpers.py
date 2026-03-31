"""Tessie helper functions."""

from collections.abc import Awaitable
from typing import Any

from aiohttp import ClientError
from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError

from . import _LOGGER
from .const import DOMAIN, TRANSLATED_ERRORS


async def handle_command(command: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    """Handle an awaitable Vehicle/EnergySite command."""
    try:
        result = await command
    except TeslaFleetError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"message": e.message},
        ) from e
    _LOGGER.debug("Command result: %s", result)
    return result


async def handle_legacy_command(command: Awaitable[dict[str, Any]], name: str) -> None:
    """Handle a legacy tessie_api command result."""
    try:
        response = await command
    except ClientError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from e
    if response["result"] is False:
        reason: str = response.get("reason", "unknown")
        translation_key = TRANSLATED_ERRORS.get(reason, "command_failed")
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"name": name, "message": reason},
        )
