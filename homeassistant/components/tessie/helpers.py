"""Tessie helper functions."""

from collections.abc import Awaitable
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import StateType

from . import _LOGGER
from .const import DOMAIN, TessieChargeStates


def charging_state_from_value(value: StateType) -> str | None:
    """Normalize charging state values from Tessie into string states."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "Charging" if value else "Stopped"
    return None


def charge_state_to_option(value: StateType) -> str | None:
    """Convert Tessie charging state values into enum sensor options."""
    if (charging_state := charging_state_from_value(value)) is None:
        return None
    return TessieChargeStates.get(charging_state)


def is_charging(value: StateType) -> bool:
    """Return if the charging state means the vehicle is charging."""
    return charging_state_from_value(value) == "Charging"


def is_charging_or_starting(value: StateType) -> bool:
    """Return if the charging state means charging can be stopped."""
    return charging_state_from_value(value) in {"Starting", "Charging"}


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
