"""Utility functions for Aqualink devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from iaqualink.exception import AqualinkServiceException

from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from collections.abc import Awaitable


async def await_or_reraise(awaitable: Awaitable) -> None:
    """Execute API call while catching service exceptions."""
    try:
        await awaitable
    except (AqualinkServiceException, httpx.HTTPError) as svc_exception:
        raise HomeAssistantError(f"Aqualink error: {svc_exception}") from svc_exception
