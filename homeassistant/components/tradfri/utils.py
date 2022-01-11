"""Util functions for IKEA Tradfri."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
from typing import Any

from pytradfri.command import Command
from pytradfri.error import PytradfriError

_LOGGER = logging.getLogger(__name__)


def _from_percentage(percentage: int) -> int:
    """Convert percent to a value that the Tradfri API understands."""
    if percentage < 20:
        # The device cannot be set to speed 5 (10%), so we should turn off the device
        # for any value below 20
        return 0

    nearest_10: int = round(percentage / 10) * 10  # Round to nearest multiple of 10
    return round(nearest_10 / 100 * 50)


def _from_fan_speed(fan_speed: int) -> int:
    """Convert the Tradfri API fan speed to a percentage value."""
    nearest_10: int = round(fan_speed / 10) * 10  # Round to nearest multiple of 10
    return round(nearest_10 / 50 * 100)


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
