"""Tessie helper functions."""

from collections.abc import Awaitable
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import StateType

from . import _LOGGER
from .const import DOMAIN, TessieChargeStates


def charge_state_to_option(value: StateType) -> str | None:
    """Convert Tessie charging state values into enum sensor options."""
    if isinstance(value, str):
        return TessieChargeStates.get(
            value, value if value in TessieChargeStates.values() else None
        )
    if isinstance(value, bool):
        return (
            TessieChargeStates["Charging"] if value else TessieChargeStates["Stopped"]
        )
    return None


async def handle_command(command: Awaitable[dict[str, Any]]) -> dict[str, Any]:
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
