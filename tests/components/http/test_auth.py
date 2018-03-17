"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access
from ipaddress import ip_network
from unittest.mock import patch

from aiohttp import BasicAuth, web
from aiohttp.web_exceptions import HTTPUnauthorized
import pytest

from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.setup import async_setup_component
from homeassistant.components.http.auth import setup_auth
from homeassistant.components.http.real_ip import setup_real_ip
from homeassistant.components.http.const import KEY_AUTHENTICATED

from . import mock_real_ip

API_PASSWORD = 'test1234'

# Don't add 127.0.0.1/::1 as trusted, as it may interfere with other test cases
TRUSTED_NETWORKS = [
    ip_network('192.0.2.0/24'),
    ip_network('2001:DB8:ABCD::/48'),
    ip_network('100.64.0.1'),
    ip_network('FD01:DB8::1'),
]
TRUSTED_ADDRESSES = ['100.64.0.1', '192.0.2.100', 'FD01:DB8::1',
                     '2001:DB8:ABCD::1']
UNTRUSTED_ADDRESSES = ['198.51.100.1', '2001:DB8:FA1::1', '127.0.0.1', '::1']


async def mock_handler(request):
    """Return if request was authenticated."""
    if not request[KEY_AUTHENTICATED]:
        raise HTTPUnauthorized
    return web.Response(status=200)


@pytest.fixture
def app():
    """Fixture to setup a web.Application."""
    app = web.Application()
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, False)
    return app


async def test_auth_middleware_loaded_by_default(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch('homeassistant.components.http.setup_auth') as mock_setup:
        await async_setup_component(hass, 'http', {
            'http': {}
        })

    assert len(mock_setup.mock_calls) == 1


async def test_access_without_password(app, aiohttp_client):
    """Test access without password."""
    setup_auth(app, [], None)
    client = await aiohttp_client(app)

    resp = await client.get('/')
    assert resp.status == 200


async def test_access_with_password_in_header(app, aiohttp_client):
    """Test access with password in URL."""
    setup_auth(app, [], API_PASSWORD)
    client = await aiohttp_client(app)

    req = await client.get(
        '/', headers={HTTP_HEADER_HA_AUTH: API_PASSWORD})
    assert req.status == 200

    req = await client.get(
        '/', headers={HTTP_HEADER_HA_AUTH: 'wrong-pass'})
    assert req.status == 401


async def test_access_with_password_in_query(app, aiohttp_client):
    """Test access without password."""
    setup_auth(app, [], API_PASSWORD)
    client = await aiohttp_client(app)

    resp = await client.get('/', params={
        'api_password': API_PASSWORD
    })
    assert resp.status == 200

    resp = await client.get('/')
    assert resp.status == 401

    resp = await client.get('/', params={
        'api_password': 'wrong-password'
    })
    assert resp.status == 401


async def test_basic_auth_works(app, aiohttp_client):
    """Test access with basic authentication."""
    setup_auth(app, [], API_PASSWORD)
    client = await aiohttp_client(app)

    req = await client.get(
        '/',
        auth=BasicAuth('homeassistant', API_PASSWORD))
    assert req.status == 200

    req = await client.get(
        '/',
        auth=BasicAuth('wrong_username', API_PASSWORD))
    assert req.status == 401

    req = await client.get(
        '/',
        auth=BasicAuth('homeassistant', 'wrong password'))
    assert req.status == 401

    req = await client.get(
        '/',
        headers={
            'authorization': 'NotBasic abcdefg'
        })
    assert req.status == 401


async def test_access_with_trusted_ip(aiohttp_client):
    """Test access with an untrusted ip address."""
    app = web.Application()
    app.router.add_get('/', mock_handler)

    setup_auth(app, TRUSTED_NETWORKS, 'some-pass')

    set_mock_ip = mock_real_ip(app)
    client = await aiohttp_client(app)

    for remote_addr in UNTRUSTED_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get('/')
        assert resp.status == 401, \
            "{} shouldn't be trusted".format(remote_addr)

    for remote_addr in TRUSTED_ADDRESSES:
        set_mock_ip(remote_addr)
        resp = await client.get('/')
        assert resp.status == 200, \
            "{} should be trusted".format(remote_addr)
