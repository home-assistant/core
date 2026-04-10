"""Helper for httpx."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import sys
from types import TracebackType
from typing import Any, Self

# httpx dynamically imports httpcore, so we need to import it
# to avoid it being imported later when the event loop is running
import httpcore  # noqa: F401
import httpx

from homeassistant.const import APPLICATION_NAME, EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.ssl import (
    SSL_ALPN_HTTP11,
    SSL_ALPN_HTTP11_HTTP2,
    SSLALPNProtocols,
    SSLCipherList,
    client_context,
    create_no_verify_ssl_context,
)

from .frame import warn_use

# We have a lot of integrations that poll every 10-30 seconds
# and we want to keep the connection open for a while so we
# don't have to reconnect every time so we use 15s to match aiohttp.
KEEP_ALIVE_TIMEOUT = 15
# Shared httpx clients keyed by (verify_ssl, alpn_protocols)
DATA_ASYNC_CLIENT: HassKey[dict[tuple[bool, SSLALPNProtocols], httpx.AsyncClient]] = (
    HassKey("httpx_async_client")
)
DEFAULT_LIMITS = limits = httpx.Limits(keepalive_expiry=KEEP_ALIVE_TIMEOUT)
SERVER_SOFTWARE = (
    f"{APPLICATION_NAME}/{__version__} "
    f"httpx/{httpx.__version__} Python/{sys.version_info[0]}.{sys.version_info[1]}"
)
USER_AGENT = "User-Agent"


@callback
@bind_hass
def get_async_client(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_HTTP11,
) -> httpx.AsyncClient:
    """Return default httpx AsyncClient.

    This method must be run in the event loop.

    Pass alpn_protocols=SSL_ALPN_HTTP11_HTTP2 to get a client configured for HTTP/2.
    Clients are cached separately by ALPN protocol to ensure proper SSL context
    configuration (ALPN protocols differ between HTTP versions).
    """
    client_key = (verify_ssl, alpn_protocols)
    clients = hass.data.setdefault(DATA_ASYNC_CLIENT, {})

    if (client := clients.get(client_key)) is None:
        client = clients[client_key] = create_async_httpx_client(
            hass, verify_ssl, alpn_protocols=alpn_protocols
        )

    return client


class HassHttpXAsyncClient(httpx.AsyncClient):
    """httpx AsyncClient that suppresses context management."""

    async def __aenter__(self) -> Self:
        """Prevent an integration from reopen of the client via context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        """Prevent an integration from close of the client via context manager."""


@callback
def create_async_httpx_client(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    ssl_cipher_list: SSLCipherList = SSLCipherList.PYTHON_DEFAULT,
    alpn_protocols: SSLALPNProtocols = SSL_ALPN_HTTP11,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient with kwargs, i.e. for cookies.

    If auto_cleanup is False, the client will be
    automatically closed on homeassistant_stop.

    Pass alpn_protocols=SSL_ALPN_HTTP11_HTTP2 for HTTP/2 support (automatically
    enables httpx http2 mode).

    This method must be run in the event loop.
    """
    # Use the requested ALPN protocols directly to ensure proper SSL context
    # bucketing. httpx/httpcore mutates SSL contexts by calling set_alpn_protocols(),
    # so we pre-set the correct protocols to prevent shared context corruption.
    ssl_context = (
        client_context(ssl_cipher_list, alpn_protocols)
        if verify_ssl
        else create_no_verify_ssl_context(ssl_cipher_list, alpn_protocols)
    )
    # Enable httpx HTTP/2 mode when HTTP/2 protocol is requested
    if alpn_protocols == SSL_ALPN_HTTP11_HTTP2:
        kwargs.setdefault("http2", True)
    client = HassHttpXAsyncClient(
        verify=ssl_context,
        headers={
            USER_AGENT: SERVER_SOFTWARE,
            **kwargs.pop("headers", {}),
        },
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
    original_aclose: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Register httpx AsyncClient aclose on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    async def _async_close_client(event: Event) -> None:
        """Close httpx client."""
        await original_aclose()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)
