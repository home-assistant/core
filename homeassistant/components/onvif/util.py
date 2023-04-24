"""ONVIF util."""
from __future__ import annotations

from zeep.exceptions import Fault


def stringify_onvif_error(error: Exception) -> str:
    """Stringify ONVIF error."""
    if isinstance(error, Fault):
        message = error.message
        if error.detail:
            message += ": " + error.detail
        if error.code:
            message += f" (code:{error.code})"
        if error.subcodes:
            message += f" (subcodes:{error.subcodes})"
        if error.actor:
            message += f" (actor:{error.actor})"
        return error.message or str(error) or "Device sent empty error"
    return str(error)


def is_auth_error(error: Exception) -> bool:
    """Return True if error is an authentication error.

    Most of the tested cameras do not return a proper error code when
    authentication fails, so we need to check the error message as well.
    """
    return (
        isinstance(error, Fault)
        and error.code == "wsse:FailedAuthentication"
        or "auth" in stringify_onvif_error(error).lower()
    )
