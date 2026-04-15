"""Compatibility wrapper for STIPS API client.

Core-bound integration code should consume communication logic from the standalone
`stips_api_bridge` package for dependency transparency.
"""

from stips_api_bridge.api import StipsApiAuthError, StipsApiClient, StipsApiError, StipsApiPermissionError

__all__ = [
    "StipsApiClient",
    "StipsApiError",
    "StipsApiAuthError",
    "StipsApiPermissionError",
]
