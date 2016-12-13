"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access
from ipaddress import ip_address
from unittest.mock import patch, mock_open

import requests

from homeassistant import bootstrap, const
import homeassistant.components.http as http
from homeassistant.components.http.const import (
    KEY_BANS_ENABLED, KEY_LOGIN_THRESHOLD, KEY_BANNED_IPS)
from homeassistant.components.http.ban import IpBan, IP_BANS_FILE

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = 'test1234'
SERVER_PORT = get_test_instance_port()
HTTP_BASE = '127.0.0.1:{}'.format(SERVER_PORT)
HTTP_BASE_URL = 'http://{}'.format(HTTP_BASE)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}
BANNED_IPS = ['200.201.202.203', '100.64.0.2']

hass = None


def _url(path=''):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


# pylint: disable=invalid-name
def setUpModule():
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    bootstrap.setup_component(
        hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_API_PASSWORD: API_PASSWORD,
                http.CONF_SERVER_PORT: SERVER_PORT,
            }
        }
    )

    bootstrap.setup_component(hass, 'api')

    hass.http.app[KEY_BANNED_IPS] = [IpBan(banned_ip) for banned_ip
                                     in BANNED_IPS]
    hass.start()


# pylint: disable=invalid-name
def tearDownModule():
    """Stop the Home Assistant server."""
    hass.stop()


class TestHttp:
    """Test HTTP component."""

    def test_access_from_banned_ip(self):
        """Test accessing to server from banned IP. Both trusted and not."""
        hass.http.app[KEY_BANS_ENABLED] = True
        for remote_addr in BANNED_IPS:
            with patch('homeassistant.components.http.'
                       'ban.get_real_ip',
                       return_value=ip_address(remote_addr)):
                req = requests.get(
                    _url(const.URL_API))
                assert req.status_code == 403

    def test_access_from_banned_ip_when_ban_is_off(self):
        """Test accessing to server from banned IP when feature is off"""
        hass.http.app[KEY_BANS_ENABLED] = False
        for remote_addr in BANNED_IPS:
            with patch('homeassistant.components.http.'
                       'ban.get_real_ip',
                       return_value=ip_address(remote_addr)):
                req = requests.get(
                    _url(const.URL_API),
                    headers={const.HTTP_HEADER_HA_AUTH: API_PASSWORD})
                assert req.status_code == 200

    def test_ip_bans_file_creation(self):
        """Testing if banned IP file created"""
        hass.http.app[KEY_BANS_ENABLED] = True
        hass.http.app[KEY_LOGIN_THRESHOLD] = 1

        m = mock_open()

        def call_server():
            with patch('homeassistant.components.http.'
                       'ban.get_real_ip',
                       return_value=ip_address("200.201.202.204")):
                print("GETTING API")
                return requests.get(
                    _url(const.URL_API),
                    headers={const.HTTP_HEADER_HA_AUTH: 'Wrong password'})

        with patch('homeassistant.components.http.ban.open', m, create=True):
            req = call_server()
            assert req.status_code == 401
            assert len(hass.http.app[KEY_BANNED_IPS]) == len(BANNED_IPS)
            assert m.call_count == 0

            req = call_server()
            assert req.status_code == 401
            assert len(hass.http.app[KEY_BANNED_IPS]) == len(BANNED_IPS) + 1
            m.assert_called_once_with(hass.config.path(IP_BANS_FILE), 'a')

            req = call_server()
            assert req.status_code == 403
            assert m.call_count == 1
