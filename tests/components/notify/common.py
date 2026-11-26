"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from typing import Any

from homeassistant.components.notify import DOMAIN, NotifyService, NotifyServiceArgument
from homeassistant.core import HomeAssistant


def send_message(
    hass: HomeAssistant, message: str, title: str | None = None, data: Any = None
) -> None:
    """Send a notification message."""
    info = {NotifyServiceArgument.MESSAGE: message}

    if title is not None:
        info[NotifyServiceArgument.TITLE] = title

    if data is not None:
        info[NotifyServiceArgument.DATA] = data

    hass.services.call(DOMAIN, NotifyService.NOTIFY, info)
