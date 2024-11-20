"""Tessie helper functions."""

from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError

from . import _LOGGER
from .const import DOMAIN


async def handle_command(command) -> dict[str, Any]:
    """Handle a command."""
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
