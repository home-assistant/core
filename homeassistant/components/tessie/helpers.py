"""Tessie helper functions."""

from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError

from . import _LOGGER


async def handle_command(command) -> dict[str, Any]:
    """Handle a command."""
    try:
        result = await command
    except TeslaFleetError as e:
        raise HomeAssistantError(f"Tessie command failed, {e.message}") from e
    _LOGGER.debug("Command result: %s", result)
    return result
