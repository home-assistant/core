"""Test real IP middleware."""
from aiohttp import web
from aiohttp.hdrs import X_FORWARDED_FOR
from ipaddress import ip_network

from homeassistant.components.http.real_ip import setup_real_ip
from homeassistant.components.http.const import KEY_REAL_IP


async def mock_handler(request):
    """Handler that returns the real IP as text."""
    return web.Response(text=str(request[KEY_REAL_IP]))


async def test_ignore_x_forwarded_for(aiohttp_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, False, [])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '255.255.255.255'
    })
    assert resp.status == 200
    text = await resp.text()
    assert text != '255.255.255.255'


async def test_use_x_forwarded_for_without_trusted_proxy(aiohttp_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, True, [])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '255.255.255.255'
    })
    assert resp.status == 200
    text = await resp.text()
    assert text != '255.255.255.255'


async def test_use_x_forwarded_for_with_trusted_proxy(aiohttp_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, True, [ip_network('127.0.0.1')])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '255.255.255.255'
    })
    assert resp.status == 200
    text = await resp.text()
    assert text == '255.255.255.255'


async def test_use_x_forwarded_for_with_untrusted_proxy(aiohttp_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, True, [ip_network('1.1.1.1')])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '255.255.255.255'
    })
    assert resp.status == 200
    text = await resp.text()
    assert text != '255.255.255.255'


async def test_use_x_forwarded_for_with_spoofed_header(aiohttp_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, True, [ip_network('127.0.0.1')])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get('/', headers={
        X_FORWARDED_FOR: '222.222.222.222, 255.255.255.255'
    })
    assert resp.status == 200
    text = await resp.text()
    assert text == '255.255.255.255'


async def test_use_x_forwarded_for_with_nonsense_header(aiohttp_client):
    """Test that we get the IP from the transport."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, True, [ip_network('127.0.0.1')])

    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get('/', headers={
        X_FORWARDED_FOR: 'This value is invalid'
    })
    assert resp.status == 200
    text = await resp.text()
    assert text == '127.0.0.1'
