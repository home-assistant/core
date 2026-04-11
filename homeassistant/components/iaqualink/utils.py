"""Utility functions for Aqualink devices."""

from __future__ import annotations

from collections.abc import Awaitable

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import AqualinkServiceException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2


async def async_get_aqualink_client(
    hass: HomeAssistant, username: str, password: str
) -> AqualinkClient:
    """Create an Aqualink client configured with Home Assistant's HTTP client."""
    return AqualinkClient(
        username,
        password,
        httpx_client=get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2),
    )


async def await_or_reraise(awaitable: Awaitable) -> None:
    """Execute API call while catching service exceptions."""
    try:
        await awaitable
    except (AqualinkServiceException, httpx.HTTPError) as svc_exception:
        raise HomeAssistantError(f"Aqualink error: {svc_exception}") from svc_exception
