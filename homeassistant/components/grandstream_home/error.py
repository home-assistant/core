"""Custom exceptions for Grandstream Home integration - re-exported from library."""

from grandstream_home_api.error import (
    GrandstreamError,
    GrandstreamHAControlDisabledError,
)

__all__ = [
    "GrandstreamError",
    "GrandstreamHAControlDisabledError",
]
