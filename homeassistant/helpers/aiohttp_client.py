"""Helper for aiohttp webclient stuff."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from functools import lru_cache
from ipaddress import ip_address
import socket
from ssl import SSLContext
import sys
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import aiohttp
from aiohttp import ClientMiddlewareType, hdrs, web
from aiohttp.hdrs import CONTENT_TYPE, USER_AGENT
from aiohttp.web_exceptions import HTTPBadGateway, HTTPGatewayTimeout
from aiohttp_asyncmdnsresolver.api import AsyncDualMDNSResolver
from yarl import URL

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import APPLICATION_NAME, EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util import ssl as ssl_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import json_loads
from homeassistant.util.network import is_loopback

from .frame import warn_use
from .json import json_dumps
from .singleton import singleton

if TYPE_CHECKING:
    from aiohttp.typedefs import JSONDecoder


DATA_CONNECTOR: HassKey[dict[tuple[bool, int, str], aiohttp.BaseConnector]] = HassKey(
    "aiohttp_connector"
)
DATA_CLIENTSESSION: HassKey[dict[tuple[bool, int, str], aiohttp.ClientSession]] = (
    HassKey("aiohttp_clientsession")
)
DATA_RESOLVER: HassKey[HassAsyncDNSResolver] = HassKey("aiohttp_resolver")

SERVER_SOFTWARE = (
    f"{APPLICATION_NAME}/{__version__} "
    f"aiohttp/{aiohttp.__version__} Python/{sys.version_info[0]}.{sys.version_info[1]}"
)

WARN_CLOSE_MSG = "closes the Home Assistant aiohttp session"

_LOCALHOST = "localhost"
_TRAILING_LOCAL_HOST = f".{_LOCALHOST}"


class SSRFRedirectError(aiohttp.ClientError):
    """SSRF redirect protection.

    Raised when a redirect targets a blocked address (loopback or unspecified).
    """


async def _ssrf_redirect_middleware(
    request: aiohttp.ClientRequest,
    handler: aiohttp.ClientHandlerType,
) -> aiohttp.ClientResponse:
    """Block redirects from non-loopback origins to loopback targets."""
    resp = await handler(request)

    # Return early if not a redirect or already loopback to allow loopback origins
    connector = request.session.connector
    if not (300 <= resp.status < 400) or await _async_is_blocked_host(
        request.url.host, connector
    ):
        return resp

    location = resp.headers.get(hdrs.LOCATION, "")
    if not location:
        return resp

    redirect_url = URL(location)
    if not redirect_url.is_absolute():
        # Relative redirects stay on the same host - always safe
        return resp

    host = redirect_url.host
    if await _async_is_blocked_host(host, connector):
        resp.close()
        raise SSRFRedirectError(
            f"Redirect from {request.url.host} to a blocked address"
            f" is not allowed: {host}"
        )

    return resp


@lru_cache
def _is_ssrf_address(address: str) -> bool:
    """Check if an IP address is a potential SSRF target.

    Returns True for loopback and unspecified addresses.
    """
    ip = ip_address(address)
    return is_loopback(ip) or ip.is_unspecified


async def _async_is_blocked_host(
    host: str | None, connector: aiohttp.BaseConnector | None
) -> bool:
    """Check if a host is blocked by hostname or by resolved IP.

    First does a fast sync check on the hostname string, then resolves
    the hostname via the connector and checks each resolved IP address.
    """
    if not host:
        return False

    # Strip FQDN trailing dot (RFC 1035) since yarl preserves it,
    # preventing an attacker from bypassing the check with "localhost."
    stripped_host = host.strip().removesuffix(".")
    if stripped_host == _LOCALHOST or stripped_host.endswith(_TRAILING_LOCAL_HOST):
        return True

    with suppress(ValueError):
        return _is_ssrf_address(host)

    if not isinstance(connector, HomeAssistantTCPConnector):
        return False

    try:
        results = await connector.async_resolve_host(host)
    except Exception:  # noqa: BLE001
        return False

    return any(_is_ssrf_address(result["host"]) for result in results)


#
# The default connection limit of 100 meant that you could only have
# 100 concurrent connections.
#
# This was effectively a limit of 100 devices and than
# the supervisor API would fail as soon as it was hit.
#
# We now apply the 100 limit per host, so that we can have 100 connections
# to a single host, but can have more than 4096 connections in total to
# prevent a single host from using all available connections.
#
MAXIMUM_CONNECTIONS = 4096
MAXIMUM_CONNECTIONS_PER_HOST = 100


class HassAsyncDNSResolver(AsyncDualMDNSResolver):
    """Home Assistant AsyncDNSResolver.

    This is a wrapper around the AsyncDualMDNSResolver to only
    close the resolver when the Home Assistant instance is closed.
    """

    async def real_close(self) -> None:
        """Close the resolver."""
        await super().close()

    async def close(self) -> None:
        """Close the resolver."""


class HassClientResponse(aiohttp.ClientResponse):
    """aiohttp.ClientResponse with a json method that uses json_loads by default."""

    async def json(
        self,
        *args: Any,
        loads: JSONDecoder = json_loads,
        **kwargs: Any,
    ) -> Any:
        """Send a json request and parse the json response."""
        return await super().json(*args, loads=loads, **kwargs)


class ChunkAsyncStreamIterator:
    """Async iterator for chunked streams.

    Based on aiohttp.streams.ChunkTupleAsyncStreamIterator, but yields
    bytes instead of tuple[bytes, bool].
    """

    __slots__ = ("_stream",)

    def __init__(self, stream: aiohttp.StreamReader) -> None:
        """Initialize."""
        self._stream = stream

    def __aiter__(self) -> Self:
        """Iterate."""
        return self

    async def __anext__(self) -> bytes:
        """Yield next chunk."""
        rv = await self._stream.readchunk()
        if rv == (b"", False):
            raise StopAsyncIteration
        return rv[0]


@callback
@bind_hass
def async_get_clientsession(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    ssl_cipher: ssl_util.SSLCipherList = ssl_util.SSLCipherList.PYTHON_DEFAULT,
) -> aiohttp.ClientSession:
    """Return default aiohttp ClientSession.

    This method must be run in the event loop.
    """
    session_key = _make_key(verify_ssl, family, ssl_cipher)
    sessions = hass.data.setdefault(DATA_CLIENTSESSION, {})

    if session_key not in sessions:
        session = _async_create_clientsession(
            hass,
            verify_ssl,
            auto_cleanup_method=_async_register_default_clientsession_shutdown,
            family=family,
            ssl_cipher=ssl_cipher,
        )
        sessions[session_key] = session
    else:
        session = sessions[session_key]

    return session


@callback
@bind_hass
def async_create_clientsession(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    ssl_cipher: ssl_util.SSLCipherList = ssl_util.SSLCipherList.PYTHON_DEFAULT,
    **kwargs: Any,
) -> aiohttp.ClientSession:
    """Create a new ClientSession with kwargs, i.e. for cookies.

    If auto_cleanup is False, you need to call detach() after the session
    returned is no longer used. Default is True, the session will be
    automatically detached on homeassistant_stop or when being created
    in config entry setup, the config entry is unloaded.

    This method must be run in the event loop.
    """
    auto_cleanup_method = None
    if auto_cleanup:
        auto_cleanup_method = _async_register_clientsession_shutdown

    return _async_create_clientsession(
        hass,
        verify_ssl,
        auto_cleanup_method=auto_cleanup_method,
        family=family,
        ssl_cipher=ssl_cipher,
        **kwargs,
    )


@callback
def _async_create_clientsession(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    auto_cleanup_method: Callable[[HomeAssistant, aiohttp.ClientSession], None]
    | None = None,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    ssl_cipher: ssl_util.SSLCipherList = ssl_util.SSLCipherList.PYTHON_DEFAULT,
    **kwargs: Any,
) -> aiohttp.ClientSession:
    """Create a new ClientSession with kwargs, i.e. for cookies."""
    middlewares: Sequence[ClientMiddlewareType] = (
        _ssrf_redirect_middleware,
        *kwargs.pop("middlewares", ()),
    )

    clientsession = aiohttp.ClientSession(
        connector=_async_get_connector(hass, verify_ssl, family, ssl_cipher),
        json_serialize=json_dumps,
        response_class=HassClientResponse,
        middlewares=middlewares,
        **kwargs,
    )
    # Prevent packages accidentally overriding our default headers
    # It's important that we identify as Home Assistant
    # If a package requires a different user agent, override it by passing a headers
    # dictionary to the request method.
    clientsession._default_headers = MappingProxyType(  # type: ignore[assignment]  # noqa: SLF001
        {USER_AGENT: SERVER_SOFTWARE},
    )

    clientsession.close = warn_use(  # type: ignore[method-assign]
        clientsession.close,
        WARN_CLOSE_MSG,
    )

    if auto_cleanup_method:
        auto_cleanup_method(hass, clientsession)

    return clientsession


@bind_hass
async def async_aiohttp_proxy_web(
    hass: HomeAssistant,
    request: web.BaseRequest,
    web_coro: Awaitable[aiohttp.ClientResponse],
    buffer_size: int = 102400,
    timeout: int = 10,
) -> web.StreamResponse | None:
    """Stream websession request to aiohttp web response."""
    try:
        async with asyncio.timeout(timeout):
            req = await web_coro

    except asyncio.CancelledError:
        # The user cancelled the request
        return None

    except TimeoutError as err:
        # Timeout trying to start the web request
        raise HTTPGatewayTimeout from err

    except aiohttp.ClientError as err:
        # Something went wrong with the connection
        raise HTTPBadGateway from err

    try:
        return await async_aiohttp_proxy_stream(
            hass, request, req.content, req.headers.get(CONTENT_TYPE)
        )
    finally:
        req.close()


@bind_hass
async def async_aiohttp_proxy_stream(
    hass: HomeAssistant,
    request: web.BaseRequest,
    stream: aiohttp.StreamReader,
    content_type: str | None,
    buffer_size: int = 102400,
    timeout: int = 10,
) -> web.StreamResponse:
    """Stream a stream to aiohttp web response."""
    response = web.StreamResponse()
    if content_type is not None:
        response.content_type = content_type
    await response.prepare(request)

    # Suppressing something went wrong fetching data, closed connection
    with suppress(TimeoutError, aiohttp.ClientError):
        while hass.is_running:
            async with asyncio.timeout(timeout):
                data = await stream.read(buffer_size)

            if not data:
                break
            await response.write(data)

    return response


@callback
def _async_register_clientsession_shutdown(
    hass: HomeAssistant, clientsession: aiohttp.ClientSession
) -> None:
    """Register ClientSession close on Home Assistant shutdown or config entry unload.

    This method must be run in the event loop.
    """

    @callback
    def _async_close_websession(*_: Any) -> None:
        """Close websession."""
        clientsession.detach()

    unsub = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_CLOSE, _async_close_websession
    )

    if not (config_entry := config_entries.current_entry.get()):
        return

    config_entry.async_on_unload(unsub)
    config_entry.async_on_unload(_async_close_websession)


@callback
def _async_register_default_clientsession_shutdown(
    hass: HomeAssistant, clientsession: aiohttp.ClientSession
) -> None:
    """Register default ClientSession close on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    @callback
    def _async_close_websession(event: Event) -> None:
        """Close websession."""
        clientsession.detach()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)


@callback
def _make_key(
    verify_ssl: bool = True,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    ssl_cipher: ssl_util.SSLCipherList = ssl_util.SSLCipherList.PYTHON_DEFAULT,
) -> tuple[bool, socket.AddressFamily, ssl_util.SSLCipherList]:
    """Make a key for connector or session pool."""
    return (verify_ssl, family, ssl_cipher)


class HomeAssistantTCPConnector(aiohttp.TCPConnector):
    """Home Assistant TCP Connector.

    Same as aiohttp.TCPConnector but with a longer cleanup_closed timeout.

    By default the cleanup_closed timeout is 2 seconds. This is too short
    for Home Assistant since we churn through a lot of connections. We set
    it to 60 seconds to reduce the overhead of aborting TLS connections
    that are likely already closed.
    """

    # abort transport after 60 seconds (cleanup broken connections)
    _cleanup_closed_period = 60.0

    async def async_resolve_host(self, host: str) -> list[aiohttp.abc.ResolveResult]:
        """Resolve a host to a list of addresses."""
        return await self._resolve_host(host, 0)


@callback
def _async_get_connector(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    ssl_cipher: ssl_util.SSLCipherList = ssl_util.SSLCipherList.PYTHON_DEFAULT,
) -> aiohttp.BaseConnector:
    """Return the connector pool for aiohttp.

    This method must be run in the event loop.
    """
    connector_key = _make_key(verify_ssl, family, ssl_cipher)
    connectors = hass.data.setdefault(DATA_CONNECTOR, {})

    if connector_key in connectors:
        return connectors[connector_key]

    if verify_ssl:
        ssl_context: SSLContext = ssl_util.client_context(
            ssl_cipher, ssl_util.SSL_ALPN_HTTP11
        )
    else:
        ssl_context = ssl_util.client_context_no_verify(
            ssl_cipher, ssl_util.SSL_ALPN_HTTP11
        )

    connector = HomeAssistantTCPConnector(
        family=family,
        ssl=ssl_context,
        limit=MAXIMUM_CONNECTIONS,
        limit_per_host=MAXIMUM_CONNECTIONS_PER_HOST,
        resolver=_async_get_or_create_resolver(hass),
    )
    connectors[connector_key] = connector

    async def _async_close_connector(event: Event) -> None:
        """Close connector pool."""
        await connector.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_connector)

    return connector


@singleton(DATA_RESOLVER)
@callback
def _async_get_or_create_resolver(hass: HomeAssistant) -> HassAsyncDNSResolver:
    """Return the HassAsyncDNSResolver."""
    resolver = _async_make_resolver(hass)

    async def _async_close_resolver(event: Event) -> None:
        await resolver.real_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_resolver)
    return resolver


@callback
def _async_make_resolver(hass: HomeAssistant) -> HassAsyncDNSResolver:
    return HassAsyncDNSResolver(async_zeroconf=zeroconf.async_get_async_zeroconf(hass))
