"""Tests for the HTTP component."""
import asyncio
from ipaddress import ip_address

from aiohttp import web

from homeassistant.components.http.const import KEY_REAL_IP


def mock_real_ip(app):
    """Inject middleware to mock real IP.

    Returns a function to set the real IP.
    """
    ip_to_mock = None

    def set_ip_to_mock(value):
        nonlocal ip_to_mock
        ip_to_mock = value

    @asyncio.coroutine
    @web.middleware
    def mock_real_ip(request, handler):
        """Mock Real IP middleware."""
        nonlocal ip_to_mock

        request[KEY_REAL_IP] = ip_address(ip_to_mock)

        return (yield from handler(request))

    @asyncio.coroutine
    def real_ip_startup(app):
        """Startup of real ip."""
        app.middlewares.insert(0, mock_real_ip)

    app.on_startup.append(real_ip_startup)

    return set_ip_to_mock
