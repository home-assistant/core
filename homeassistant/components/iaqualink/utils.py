"""Utility functions for Aqualink devices."""
from __future__ import annotations

from collections.abc import Awaitable

from iaqualink.exception import AqualinkServiceException

from homeassistant.exceptions import HomeAssistantError


async def await_or_reraise(awaitable: Awaitable) -> None:
    """Execute API call while catching service exceptions."""
    try:
        await awaitable
    except AqualinkServiceException as svc_exception:
        raise HomeAssistantError(f"Aqualink error: {svc_exception}") from svc_exception
