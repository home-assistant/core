"""Util functions for IKEA Tradfri."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any

from pytradfri.command import Command
from pytradfri.error import PytradfriError

from .const import ATTR_MAX_FAN_STEPS

_LOGGER = logging.getLogger(__name__)


def _from_fan_percentage(percentage: int) -> int:
    """Convert percent to a value that the Tradfri API understands."""
    return round(percentage / 100 * ATTR_MAX_FAN_STEPS)


def _from_fan_speed(fan_speed: int) -> int:
    """Convert the Tradfri API fan speed to a percentage value."""
    return round(fan_speed / ATTR_MAX_FAN_STEPS * 100)


def tradfri_handle_api_error(
    func: Callable[[Command | list[Command]], Any]
) -> Callable[[str], Any]:
    """Handle tradfri api call error."""

    @wraps(func)
    async def wrapper(command: Command | list[Command]) -> None:
        """Decorate api call."""
        try:
            await func(command)
        except PytradfriError as err:
            _LOGGER.error("Unable to execute command %s: %s", command, err)

    return wrapper
