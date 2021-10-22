"""The lookin integration exceptions."""
from __future__ import annotations

__all__ = ("NoUsableService",)


class NoUsableService(Exception):
    """Error to indicate device could not be found."""
