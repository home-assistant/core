"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access
from unittest.mock import patch, mock_open

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized

from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
from homeassistant.components.http.ban import (
    IpBan, IP_BANS_FILE, setup_bans, KEY_BANNED_IPS)

from . import mock_real_ip

BANNED_IPS = ['200.201.202.203', '100.64.0.2']


async def test_access_from_banned_ip(hass, test_client):
    """Test accessing to server from banned IP. Both trusted and not."""
    app = web.Application()
    setup_bans(hass, app, 5)
    set_real_ip = mock_real_ip(app)

    with patch('homeassistant.components.http.ban.load_ip_bans_config',
               return_value=[IpBan(banned_ip) for banned_ip
                             in BANNED_IPS]):
        client = await test_client(app)

    for remote_addr in BANNED_IPS:
        set_real_ip(remote_addr)
        resp = await client.get('/')
        assert resp.status == 403


async def test_ban_middleware_not_loaded_by_config(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch('homeassistant.components.http.setup_bans') as mock_setup:
        await async_setup_component(hass, 'http', {
            'http': {
                http.CONF_IP_BAN_ENABLED: False,
            }
        })

    assert len(mock_setup.mock_calls) == 0


async def test_ban_middleware_loaded_by_default(hass):
    """Test accessing to server from banned IP when feature is off."""
    with patch('homeassistant.components.http.setup_bans') as mock_setup:
        await async_setup_component(hass, 'http', {
            'http': {}
        })

    assert len(mock_setup.mock_calls) == 1


async def test_ip_bans_file_creation(hass, test_client):
    """Testing if banned IP file created."""
    app = web.Application()
    app['hass'] = hass

    async def unauth_handler(request):
        """Return a mock web response."""
        raise HTTPUnauthorized

    app.router.add_get('/', unauth_handler)
    setup_bans(hass, app, 1)
    mock_real_ip(app)("200.201.202.204")

    with patch('homeassistant.components.http.ban.load_ip_bans_config',
               return_value=[IpBan(banned_ip) for banned_ip
                             in BANNED_IPS]):
        client = await test_client(app)

    m = mock_open()

    with patch('homeassistant.components.http.ban.open', m, create=True):
        resp = await client.get('/')
        assert resp.status == 401
        assert len(app[KEY_BANNED_IPS]) == len(BANNED_IPS)
        assert m.call_count == 0

        resp = await client.get('/')
        assert resp.status == 401
        assert len(app[KEY_BANNED_IPS]) == len(BANNED_IPS) + 1
        m.assert_called_once_with(hass.config.path(IP_BANS_FILE), 'a')

        resp = await client.get('/')
        assert resp.status == 403
        assert m.call_count == 1
