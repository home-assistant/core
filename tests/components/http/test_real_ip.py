"""Test real IP middleware."""
import asyncio

from aiohttp import web
from aiohttp.hdrs import X_FORWARDED_FOR

from homeassistant.components.http.real_ip import setup_real_ip
from homeassistant.components.http.const import KEY_REAL_IP


@asyncio.coroutine
def mock_handler(request):
    """Handler that returns the real IP as text."""
    return web.Response(text=str(request[KEY_REAL_IP]))


@asyncio.coroutine
def test_ignore_x_forwarded_for(test_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, False)

    mock_api_client = yield from test_client(app)

    resp = yield from mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '255.255.255.255'
    })
    assert resp.status == 200
    text = yield from resp.text()
    assert text != '255.255.255.255'


@asyncio.coroutine
def test_use_x_forwarded_for(test_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, True)

    mock_api_client = yield from test_client(app)

    resp = yield from mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '255.255.255.255'
    })
    assert resp.status == 200
    text = yield from resp.text()
    assert text == '255.255.255.255'
