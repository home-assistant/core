"""The tests for the Home Assistant HTTP component."""
from datetime import timedelta
from ipaddress import ip_network
from unittest.mock import patch

import pytest
from aiohttp import BasicAuth, web
from aiohttp.web_exceptions import HTTPUnauthorized

from homeassistant.components.http.auth import setup_auth, async_sign_path
from homeassistant.components.http.const import KEY_AUTHENTICATED
from homeassistant.components.http.real_ip import setup_real_ip
from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.setup import async_setup_component
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

    token = request.get('hass_refresh_token')
    token_id = token.id if token else None
    user = request.get('hass_user')
    user_id = user.id if user else None

    return web.json_response(status=200, data={
        'refresh_token_id': token_id,
        'user_id': user_id,
    })


@pytest.fixture
def app(hass):
    """Fixture to set up a web.Application."""
    app = web.Application()
    app['hass'] = hass
    app.router.add_get('/', mock_handler)
    setup_real_ip(app, False, [])
    return app


@pytest.fixture
def app2(hass):
    """Fixture to set up a web.Application without real_ip middleware."""
    app = web.Application()
    app['hass'] = hass
    app.router.add_get('/', mock_handler)
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
    setup_auth(app, [], False, api_password=None)
    client = await aiohttp_client(app)

    resp = await client.get('/')
    assert resp.status == 200


async def test_access_with_password_in_header(app, aiohttp_client):
    """Test access with password in header."""
    setup_auth(app, [], False, api_password=API_PASSWORD)
    client = await aiohttp_client(app)

    req = await client.get(
        '/', headers={HTTP_HEADER_HA_AUTH: API_PASSWORD})
    assert req.status == 200

    req = await client.get(
        '/', headers={HTTP_HEADER_HA_AUTH: 'wrong-pass'})
    assert req.status == 401


async def test_access_with_password_in_query(app, aiohttp_client):
    """Test access with password in URL."""
    setup_auth(app, [], False, api_password=API_PASSWORD)
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
    setup_auth(app, [], False, api_password=API_PASSWORD)
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


async def test_access_with_trusted_ip(app2, aiohttp_client):
    """Test access with an untrusted ip address."""
    setup_auth(app2, TRUSTED_NETWORKS, False, api_password='some-pass')

    set_mock_ip = mock_real_ip(app2)
    client = await aiohttp_client(app2)

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


async def test_auth_active_access_with_access_token_in_header(
        hass, app, aiohttp_client, hass_access_token):
    """Test access with access token in header."""
    token = hass_access_token
    setup_auth(app, [], True, api_password=None)
    client = await aiohttp_client(app)

    req = await client.get(
        '/', headers={'Authorization': 'Bearer {}'.format(token)})
    assert req.status == 200

    req = await client.get(
        '/', headers={'AUTHORIZATION': 'Bearer {}'.format(token)})
    assert req.status == 200

    req = await client.get(
        '/', headers={'authorization': 'Bearer {}'.format(token)})
    assert req.status == 200

    req = await client.get(
        '/', headers={'Authorization': token})
    assert req.status == 401

    req = await client.get(
        '/', headers={'Authorization': 'BEARER {}'.format(token)})
    assert req.status == 401

    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    refresh_token.user.is_active = False
    req = await client.get(
        '/', headers={'Authorization': 'Bearer {}'.format(token)})
    assert req.status == 401


async def test_auth_active_access_with_trusted_ip(app2, aiohttp_client):
    """Test access with an untrusted ip address."""
    setup_auth(app2, TRUSTED_NETWORKS, True, api_password=None)

    set_mock_ip = mock_real_ip(app2)
    client = await aiohttp_client(app2)

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


async def test_auth_active_blocked_api_password_access(app, aiohttp_client):
    """Test access using api_password should be blocked when auth.active."""
    setup_auth(app, [], True, api_password=API_PASSWORD)
    client = await aiohttp_client(app)

    req = await client.get(
        '/', headers={HTTP_HEADER_HA_AUTH: API_PASSWORD})
    assert req.status == 401

    resp = await client.get('/', params={
        'api_password': API_PASSWORD
    })
    assert resp.status == 401

    req = await client.get(
        '/',
        auth=BasicAuth('homeassistant', API_PASSWORD))
    assert req.status == 401


async def test_auth_legacy_support_api_password_access(app, aiohttp_client):
    """Test access using api_password if auth.support_legacy."""
    setup_auth(app, [], True, support_legacy=True, api_password=API_PASSWORD)
    client = await aiohttp_client(app)

    req = await client.get(
        '/', headers={HTTP_HEADER_HA_AUTH: API_PASSWORD})
    assert req.status == 200

    resp = await client.get('/', params={
        'api_password': API_PASSWORD
    })
    assert resp.status == 200

    req = await client.get(
        '/',
        auth=BasicAuth('homeassistant', API_PASSWORD))
    assert req.status == 200


async def test_auth_access_signed_path(
        hass, app, aiohttp_client, hass_access_token):
    """Test access with signed url."""
    app.router.add_post('/', mock_handler)
    app.router.add_get('/another_path', mock_handler)
    setup_auth(app, [], True, api_password=None)
    client = await aiohttp_client(app)

    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)

    signed_path = async_sign_path(
        hass, refresh_token.id, '/', timedelta(seconds=5)
    )

    req = await client.get(signed_path)
    assert req.status == 200
    data = await req.json()
    assert data['refresh_token_id'] == refresh_token.id
    assert data['user_id'] == refresh_token.user.id

    # Use signature on other path
    req = await client.get(
        '/another_path?{}'.format(signed_path.split('?')[1]))
    assert req.status == 401

    # We only allow GET
    req = await client.post(signed_path)
    assert req.status == 401

    # Never valid as expired in the past.
    expired_signed_path = async_sign_path(
        hass, refresh_token.id, '/', timedelta(seconds=-5)
    )

    req = await client.get(expired_signed_path)
    assert req.status == 401

    # refresh token gone should also invalidate signature
    await hass.auth.async_remove_refresh_token(refresh_token)
    req = await client.get(signed_path)
    assert req.status == 401
