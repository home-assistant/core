"""Helper methods for common tasks."""
from __future__ import annotations

import functools as ft
import logging
from typing import Any, Callable

from pysonos.exceptions import SoCoException, SoCoUPnPException

from homeassistant.exceptions import HomeAssistantError

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
