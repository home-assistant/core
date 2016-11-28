"""Helper for aiohttp webclient stuff."""
import asyncio

import aiohttp

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP


DATA_CONNECTOR = 'aiohttp_connector'
DATA_CONNECTOR_NOTVERIFY = 'aiohttp_connector_notverify'
DATA_CLIENTSESSION = 'aiohttp_clientsession'
DATA_CLIENTSESSION_NOTVERIFY = 'aiohttp_clientsession_notverify'


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
            connector=connector
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
        **kwargs
    )

    if auto_cleanup:
        _async_register_clientsession_shutdown(hass, clientsession)

    return clientsession


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
        EVENT_HOMEASSISTANT_STOP, _async_close_websession)


@callback
def _async_get_connector(hass, verify_ssl=True):
    """Return the connector pool for aiohttp.

    This method must be run in the event loop.
    """
    if verify_ssl:
        if DATA_CONNECTOR not in hass.data:
            connector = aiohttp.TCPConnector(loop=hass.loop)
            hass.data[DATA_CONNECTOR] = connector

            _async_register_connector_shutdown(hass, connector)
        else:
            connector = hass.data[DATA_CONNECTOR]
    else:
        if DATA_CONNECTOR_NOTVERIFY not in hass.data:
            connector = aiohttp.TCPConnector(loop=hass.loop, verify_ssl=False)
            hass.data[DATA_CONNECTOR_NOTVERIFY] = connector

            _async_register_connector_shutdown(hass, connector)
        else:
            connector = hass.data[DATA_CONNECTOR_NOTVERIFY]

    return connector


@callback
# pylint: disable=invalid-name
def _async_register_connector_shutdown(hass, connector):
    """Register connector pool close on homeassistant shutdown.

    This method must be run in the event loop.
    """
    @asyncio.coroutine
    def _async_close_connector(event):
        """Close websession on shutdown."""
        yield from connector.close()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _async_close_connector)
