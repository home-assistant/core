"""Helper for aiohttp webclient stuff."""
import asyncio
import sys

import aiohttp
from aiohttp.hdrs import USER_AGENT, CONTENT_TYPE
from aiohttp import web
from aiohttp.web_exceptions import HTTPGatewayTimeout
import async_timeout

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.const import __version__

DATA_CONNECTOR = 'aiohttp_connector'
DATA_CONNECTOR_NOTVERIFY = 'aiohttp_connector_notverify'
DATA_CLIENTSESSION = 'aiohttp_clientsession'
DATA_CLIENTSESSION_NOTVERIFY = 'aiohttp_clientsession_notverify'
SERVER_SOFTWARE = 'HomeAssistant/{0} aiohttp/{1} Python/{2[0]}.{2[1]}'.format(
    __version__, aiohttp.__version__, sys.version_info)


@callback
def async_get_clientsession(hass, verify_ssl=True):
    """Return default aiohttp ClientSession.

    This method must be run in the event loop.
    """
    if verify_ssl:
        key = DATA_CLIENTSESSION
    else:
        key = DATA_CLIENTSESSION_NOTVERIFY

    if key not in hass.data:
        connector = _async_get_connector(hass, verify_ssl)
        clientsession = aiohttp.ClientSession(
            loop=hass.loop,
            connector=connector,
            headers={USER_AGENT: SERVER_SOFTWARE}
        )
        _async_register_clientsession_shutdown(hass, clientsession)
        hass.data[key] = clientsession

    return hass.data[key]


@callback
def async_create_clientsession(hass, verify_ssl=True, auto_cleanup=True,
                               **kwargs):
    """Create a new ClientSession with kwargs, i.e. for cookies.

    If auto_cleanup is False, you need to call detach() after the session
    returned is no longer used. Default is True, the session will be
    automatically detached on homeassistant_stop.

    This method must be run in the event loop.
    """
    connector = _async_get_connector(hass, verify_ssl)

    clientsession = aiohttp.ClientSession(
        loop=hass.loop,
        connector=connector,
        headers={USER_AGENT: SERVER_SOFTWARE},
        **kwargs
    )

    if auto_cleanup:
        _async_register_clientsession_shutdown(hass, clientsession)

    return clientsession


@asyncio.coroutine
def async_aiohttp_proxy_stream(hass, request, stream_coro, buffer_size=102400,
                               timeout=10):
    """Stream websession request to aiohttp web response."""
    response = None
    stream = None

    try:
        with async_timeout.timeout(timeout, loop=hass.loop):
            stream = yield from stream_coro

        response = web.StreamResponse()
        response.content_type = stream.headers.get(CONTENT_TYPE)

        yield from response.prepare(request)

        while True:
            data = yield from stream.content.read(buffer_size)
            if not data:
                break
            response.write(data)

    except asyncio.TimeoutError:
        raise HTTPGatewayTimeout()

    except (aiohttp.errors.ClientError,
            aiohttp.errors.ClientDisconnectedError):
        pass

    except (asyncio.CancelledError, ConnectionResetError):
        response = None

    finally:
        if stream is not None:
            stream.close()
        if response is not None:
            yield from response.write_eof()


@callback
# pylint: disable=invalid-name
def _async_register_clientsession_shutdown(hass, clientsession):
    """Register ClientSession close on homeassistant shutdown.

    This method must be run in the event loop.
    """
    @callback
    def _async_close_websession(event):
        """Close websession."""
        clientsession.detach()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_CLOSE, _async_close_websession)


@callback
def _async_get_connector(hass, verify_ssl=True):
    """Return the connector pool for aiohttp.

    This method must be run in the event loop.
    """
    is_new = False

    if verify_ssl:
        if DATA_CONNECTOR not in hass.data:
            connector = aiohttp.TCPConnector(loop=hass.loop)
            hass.data[DATA_CONNECTOR] = connector
            is_new = True
        else:
            connector = hass.data[DATA_CONNECTOR]
    else:
        if DATA_CONNECTOR_NOTVERIFY not in hass.data:
            connector = aiohttp.TCPConnector(loop=hass.loop, verify_ssl=False)
            hass.data[DATA_CONNECTOR_NOTVERIFY] = connector
            is_new = True
        else:
            connector = hass.data[DATA_CONNECTOR_NOTVERIFY]

    if is_new:
        @asyncio.coroutine
        def _async_close_connector(event):
            """Close connector pool."""
            yield from connector.close()

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_CLOSE, _async_close_connector)

    return connector
