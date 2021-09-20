"""Helper methods for common tasks."""
from __future__ import annotations

import functools as ft
import logging
from typing import Any, Callable

from pysonos.exceptions import SoCoException, SoCoUPnPException

_LOGGER = logging.getLogger(__name__)


def soco_error(errorcodes: list[str] | None = None) -> Callable:
    """Filter out specified UPnP errors from logs and avoid exceptions."""

    def decorator(funct: Callable) -> Callable:
        """Decorate functions."""

        @ft.wraps(funct)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrap for all soco UPnP exception."""
            try:
                return funct(*args, **kwargs)
            except SoCoUPnPException as err:
                if not errorcodes or err.error_code not in errorcodes:
                    _LOGGER.error("Error on %s with %s", funct.__name__, err)
            except SoCoException as err:
                _LOGGER.error("Error on %s with %s", funct.__name__, err)

        return wrapper

    return decorator
