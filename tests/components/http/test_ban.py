"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access
import asyncio
from ipaddress import ip_address
from unittest.mock import patch, mock_open

import pytest

from homeassistant import const
from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
from homeassistant.components.http.const import (
    KEY_BANS_ENABLED, KEY_LOGIN_THRESHOLD, KEY_BANNED_IPS)
from homeassistant.components.http.ban import IpBan, IP_BANS_FILE

API_PASSWORD = 'test1234'
BANNED_IPS = ['200.201.202.203', '100.64.0.2']


@pytest.fixture
def mock_api_client(hass, test_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'api', {
        'http': {
            http.CONF_API_PASSWORD: API_PASSWORD,
        }
    }))
    hass.http.app[KEY_BANNED_IPS] = [IpBan(banned_ip) for banned_ip
                                     in BANNED_IPS]
    return hass.loop.run_until_complete(test_client(hass.http.app))


@asyncio.coroutine
def test_access_from_banned_ip(hass, mock_api_client):
    """Test accessing to server from banned IP. Both trusted and not."""
    hass.http.app[KEY_BANS_ENABLED] = True
    for remote_addr in BANNED_IPS:
        with patch('homeassistant.components.http.'
                   'ban.get_real_ip',
                   return_value=ip_address(remote_addr)):
            resp = yield from mock_api_client.get(
                const.URL_API)
            assert resp.status == 403


@asyncio.coroutine
def test_access_from_banned_ip_when_ban_is_off(hass, mock_api_client):
    """Test accessing to server from banned IP when feature is off."""
    hass.http.app[KEY_BANS_ENABLED] = False
    for remote_addr in BANNED_IPS:
        with patch('homeassistant.components.http.'
                   'ban.get_real_ip',
                   return_value=ip_address(remote_addr)):
            resp = yield from mock_api_client.get(
                const.URL_API,
                headers={const.HTTP_HEADER_HA_AUTH: API_PASSWORD})
            assert resp.status == 200


@asyncio.coroutine
def test_ip_bans_file_creation(hass, mock_api_client):
    """Testing if banned IP file created."""
    hass.http.app[KEY_BANS_ENABLED] = True
    hass.http.app[KEY_LOGIN_THRESHOLD] = 1

    m = mock_open()

    @asyncio.coroutine
    def call_server():
        with patch('homeassistant.components.http.'
                   'ban.get_real_ip',
                   return_value=ip_address("200.201.202.204")):
            resp = yield from mock_api_client.get(
                const.URL_API,
                headers={const.HTTP_HEADER_HA_AUTH: 'Wrong password'})
            return resp

    with patch('homeassistant.components.http.ban.open', m, create=True):
        resp = yield from call_server()
        assert resp.status == 401
        assert len(hass.http.app[KEY_BANNED_IPS]) == len(BANNED_IPS)
        assert m.call_count == 0

        resp = yield from call_server()
        assert resp.status == 401
        assert len(hass.http.app[KEY_BANNED_IPS]) == len(BANNED_IPS) + 1
        m.assert_called_once_with(hass.config.path(IP_BANS_FILE), 'a')

        resp = yield from call_server()
        assert resp.status == 403
        assert m.call_count == 1
