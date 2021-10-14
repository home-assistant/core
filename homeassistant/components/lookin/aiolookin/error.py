"""The lookin integration exceptions."""
from __future__ import annotations

__all__ = (
    "NoUsableService",
    "DeviceNotFound",
)


class NoUsableService(Exception):
    """Error to indicate device could not be found."""


class DeviceNotFound(Exception):
    """Error to indicate device could not be found."""
