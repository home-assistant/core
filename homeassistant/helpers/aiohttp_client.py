"""Helper for aiohttp webclient stuff."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from ssl import SSLContext
import sys
from typing import Any, Awaitable, cast

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE, USER_AGENT
from aiohttp.web_exceptions import HTTPBadGateway, HTTPGatewayTimeout
import async_timeout

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, __version__
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.frame import warn_use
from homeassistant.loader import bind_hass
from homeassistant.util import ssl as ssl_util

DATA_CONNECTOR = "aiohttp_connector"
DATA_CONNECTOR_NOTVERIFY = "aiohttp_connector_notverify"
DATA_CLIENTSESSION = "aiohttp_clientsession"
DATA_CLIENTSESSION_NOTVERIFY = "aiohttp_clientsession_notverify"
SERVER_SOFTWARE = "HomeAssistant/{0} aiohttp/{1} Python/{2[0]}.{2[1]}".format(
    __version__, aiohttp.__version__, sys.version_info
)


@callback
@bind_hass
def async_get_clientsession(
    hass: HomeAssistant, verify_ssl: bool = False
) -> aiohttp.ClientSession:
    """Return default aiohttp ClientSession.

    This method must be run in the event loop.
    """
    key = DATA_CLIENTSESSION_NOTVERIFY
    if verify_ssl:
        key = DATA_CLIENTSESSION

    if key not in hass.data:
        hass.data[key] = async_create_clientsession(hass, verify_ssl)

    return cast(aiohttp.ClientSession, hass.data[key])


@callback
@bind_hass
def async_create_clientsession(
    hass: HomeAssistant,
    verify_ssl: bool = True,
    auto_cleanup: bool = True,
    **kwargs: Any,
) -> aiohttp.ClientSession:
    """Create a new ClientSession with kwargs, i.e. for cookies.

    If auto_cleanup is False, you need to call detach() after the session
    returned is no longer used. Default is True, the session will be
    automatically detached on homeassistant_stop.

    This method must be run in the event loop.
    """
    connector = _async_get_connector(hass, verify_ssl)

    clientsession = aiohttp.ClientSession(
        connector=connector,
        headers={USER_AGENT: SERVER_SOFTWARE},
        **kwargs,
    )

    clientsession.close = warn_use(  # type: ignore
        clientsession.close, "closes the Home Assistant aiohttp session"
    )

    if auto_cleanup:
        _async_register_clientsession_shutdown(hass, clientsession)

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
        with async_timeout.timeout(timeout):
            req = await web_coro

    except asyncio.CancelledError:
        # The user cancelled the request
        return None

    except asyncio.TimeoutError as err:
        # Timeout trying to start the web request
        raise HTTPGatewayTimeout() from err

    except aiohttp.ClientError as err:
        # Something went wrong with the connection
        raise HTTPBadGateway() from err

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
    with suppress(asyncio.TimeoutError, aiohttp.ClientError):
        while hass.is_running:
            with async_timeout.timeout(timeout):
                data = await stream.read(buffer_size)

            if not data:
                break
            await response.write(data)

    return response


@callback
def _async_register_clientsession_shutdown(
    hass: HomeAssistant, clientsession: aiohttp.ClientSession
) -> None:
    """Register ClientSession close on Home Assistant shutdown.

    This method must be run in the event loop.
    """

    @callback
    def _async_close_websession(event: Event) -> None:
        """Close websession."""
        clientsession.detach()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)


@callback
def _async_get_connector(
    hass: HomeAssistant, verify_ssl: bool = True
) -> aiohttp.BaseConnector:
    """Return the connector pool for aiohttp.

    This method must be run in the event loop.
    """
    key = DATA_CONNECTOR if verify_ssl else DATA_CONNECTOR_NOTVERIFY

    if key in hass.data:
        return cast(aiohttp.BaseConnector, hass.data[key])

    if verify_ssl:
        ssl_context: bool | SSLContext = ssl_util.client_context()
    else:
        ssl_context = False

    connector = aiohttp.TCPConnector(enable_cleanup_closed=True, ssl=ssl_context)
    hass.data[key] = connector

    async def _async_close_connector(event: Event) -> None:
        """Close connector pool."""
        await connector.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_connector)

    return connector
