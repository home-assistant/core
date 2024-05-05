"""Helper for httpx."""

from __future__ import annotations

from collections.abc import Callable
import sys
from typing import Any, Self

import httpx

from homeassistant.const import APPLICATION_NAME, EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util.ssl import (
    SSLCipherList,
    client_context,
    create_no_verify_ssl_context,
)

from .frame import warn_use

# We have a lot of integrations that poll every 10-30 seconds
# and we want to keep the connection open for a while so we
# don't have to reconnect every time so we use 15s to match aiohttp.
KEEP_ALIVE_TIMEOUT = 15
DATA_ASYNC_CLIENT = "httpx_async_client"
DATA_ASYNC_CLIENT_NOVERIFY = "httpx_async_client_noverify"
DEFAULT_LIMITS = limits = httpx.Limits(keepalive_expiry=KEEP_ALIVE_TIMEOUT)
SERVER_SOFTWARE = (
    f"{APPLICATION_NAME}/{__version__} "
    f"httpx/{httpx.__version__} Python/{sys.version_info[0]}.{sys.version_info[1]}"
)
USER_AGENT = "User-Agent"


@callback
@bind_hass
def get_async_client(hass: HomeAssistant, verify_ssl: bool = True) -> httpx.AsyncClient:
    """Return default httpx AsyncClient.

    This method must be run in the event loop.
    """
    key = DATA_ASYNC_CLIENT if verify_ssl else DATA_ASYNC_CLIENT_NOVERIFY

    client: httpx.AsyncClient | None = hass.data.get(key)

    if client is None:
        client = hass.data[key] = create_async_httpx_client(hass, verify_ssl)

    return client


class HassHttpXAsyncClient(httpx.AsyncClient):
    """httpx AsyncClient that suppresses context management."""

    async def __aenter__(self) -> Self:
        """Prevent an integration from reopen of the client via context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Prevent an integration from close of the client via context manager."""


@callback
def create_async_httpx_client(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient with kwargs, i.e. for cookies.

    If auto_cleanup is False, the client will be
    automatically closed on homeassistant_stop.

    This method must be run in the event loop.
    """
    ssl_context = (
        client_context(ssl_cipher_list)
        if verify_ssl
        else create_no_verify_ssl_context(ssl_cipher_list)
    )
    client = HassHttpXAsyncClient(
        verify=ssl_context,
        headers={USER_AGENT: SERVER_SOFTWARE},
        limits=DEFAULT_LIMITS,
        **kwargs,
    )

    original_aclose = client.aclose

    client.aclose = warn_use(  # type: ignore[method-assign]
        client.aclose, "closes the Home Assistant httpx client"
    )

    if auto_cleanup:
        _async_register_async_client_shutdown(hass, client, original_aclose)

    return client


@callback
def _async_register_async_client_shutdown(
    hass: HomeAssistant,
    client: httpx.AsyncClient,
    original_aclose: Callable[..., Any],
) -> None:
    """Register httpx AsyncClient aclose on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    async def _async_close_client(event: Event) -> None:
        """Close httpx client."""
        await original_aclose()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)
