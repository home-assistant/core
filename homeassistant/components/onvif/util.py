"""ONVIF util."""
from __future__ import annotations

from typing import Any

from zeep.exceptions import Fault


def extract_subcodes_as_strings(subcodes: Any) -> list[str]:
    """Stringify ONVIF subcodes."""
    if isinstance(subcodes, list):
        return [code.text if hasattr(code, "text") else str(code) for code in subcodes]
    return [str(subcodes)]


def stringify_onvif_error(error: Exception) -> str:
    """Stringify ONVIF error."""
    if isinstance(error, Fault):
        message = error.message
        if error.detail:
            message += ": " + error.detail
        if error.code:
            message += f" (code:{error.code})"
        if error.subcodes:
            message += (
                f" (subcodes:{','.join(extract_subcodes_as_strings(error.subcodes))})"
            )
        if error.actor:
            message += f" (actor:{error.actor})"
    else:
        message = str(error)
    return message or "Device sent empty error"


def is_auth_error(error: Exception) -> bool:
    """Return True if error is an authentication error.

    Most of the tested cameras do not return a proper error code when
    authentication fails, so we need to check the error message as well.
    """
    if not isinstance(error, Fault):
        return False
    return (
        any(
            "NotAuthorized" in code
            for code in extract_subcodes_as_strings(error.subcodes)
        )
        or "auth" in stringify_onvif_error(error).lower()
    )
