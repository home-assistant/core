"""Helper methods for common tasks."""
from __future__ import annotations

import functools as ft
import logging
from typing import Any, Callable

from pysonos.exceptions import SoCoException, SoCoUPnPException

from homeassistant.exceptions import HomeAssistantError

UID_PREFIX = "RINCON_"
UID_POSTFIX = "01400"

_LOGGER = logging.getLogger(__name__)


def soco_error(errorcodes: list[str] | None = None) -> Callable:
    """Filter out specified UPnP errors and raise exceptions for service calls."""

    def decorator(funct: Callable) -> Callable:
        """Decorate functions."""

        @ft.wraps(funct)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrap for all soco UPnP exception."""
            try:
                return funct(*args, **kwargs)
            except (OSError, SoCoException, SoCoUPnPException) as err:
                error_code = getattr(err, "error_code", None)
                function = funct.__name__
                if errorcodes and error_code in errorcodes:
                    _LOGGER.debug(
                        "Error code %s ignored in call to %s", error_code, function
                    )
                    return
                raise HomeAssistantError(f"Error calling {function}: {err}") from err

        return wrapper

    return decorator


def uid_to_short_hostname(uid: str) -> str:
    """Convert a Sonos uid to a short hostname."""
    hostname_uid = uid
    if hostname_uid.startswith(UID_PREFIX):
        hostname_uid = hostname_uid[len(UID_PREFIX) :]
    if hostname_uid.endswith(UID_POSTFIX):
        hostname_uid = hostname_uid[: -len(UID_POSTFIX)]
    return f"Sonos-{hostname_uid}"


def hostname_to_uid(hostname: str) -> str:
    """Convert a Sonos hostname to a uid."""
    baseuid = hostname.split("-")[1].replace(".local.", "")
    return f"{UID_PREFIX}{baseuid}{UID_POSTFIX}"
