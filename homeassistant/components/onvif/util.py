"""ONVIF util."""
from __future__ import annotations

from zeep.exceptions import Fault


def stringify_onvif_error(error: Exception) -> str:
    """Stringify ONVIF error."""
    if isinstance(error, Fault):
        return error.message or str(error) or "Device sent empty error"
    return str(error)
