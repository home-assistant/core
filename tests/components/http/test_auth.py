"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access
import asyncio
from ipaddress import ip_address, ip_network
from unittest.mock import patch

import pytest

from homeassistant import const
from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
from homeassistant.components.http.const import (
    KEY_TRUSTED_NETWORKS, KEY_USE_X_FORWARDED_FOR, HTTP_HEADER_X_FORWARDED_FOR)

API_PASSWORD = 'test1234'

# Don't add 127.0.0.1/::1 as trusted, as it may interfere with other test cases
TRUSTED_NETWORKS = ['192.0.2.0/24', '2001:DB8:ABCD::/48', '100.64.0.1',
                    'FD01:DB8::1']
TRUSTED_ADDRESSES = ['100.64.0.1', '192.0.2.100', 'FD01:DB8::1',
                     '2001:DB8:ABCD::1']
UNTRUSTED_ADDRESSES = ['198.51.100.1', '2001:DB8:FA1::1', '127.0.0.1', '::1']


@pytest.fixture
def mock_api_client(hass, test_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'api', {
        'http': {
            http.CONF_API_PASSWORD: API_PASSWORD,
        }
    }))
    return hass.loop.run_until_complete(test_client(hass.http.app))


@pytest.fixture
def mock_trusted_networks(hass, mock_api_client):
    """Mock trusted networks."""
    hass.http.app[KEY_TRUSTED_NETWORKS] = [
        ip_network(trusted_network)
        for trusted_network in TRUSTED_NETWORKS]


@asyncio.coroutine
def test_access_denied_without_password(mock_api_client):
    """Test access without password."""
    resp = yield from mock_api_client.get(const.URL_API)
    assert resp.status == 401


@asyncio.coroutine
def test_access_denied_with_wrong_password_in_header(mock_api_client):
    """Test access with wrong password."""
    resp = yield from mock_api_client.get(const.URL_API, headers={
        const.HTTP_HEADER_HA_AUTH: 'wrongpassword'
    })
    assert resp.status == 401


@asyncio.coroutine
def test_access_denied_with_x_forwarded_for(hass, mock_api_client,
                                            mock_trusted_networks):
    """Test access denied through the X-Forwarded-For http header."""
    hass.http.use_x_forwarded_for = True
    for remote_addr in UNTRUSTED_ADDRESSES:
        resp = yield from mock_api_client.get(const.URL_API, headers={
            HTTP_HEADER_X_FORWARDED_FOR: remote_addr})

        assert resp.status == 401, \
            "{} shouldn't be trusted".format(remote_addr)


@asyncio.coroutine
def test_access_denied_with_untrusted_ip(mock_api_client,
                                         mock_trusted_networks):
    """Test access with an untrusted ip address."""
    for remote_addr in UNTRUSTED_ADDRESSES:
        with patch('homeassistant.components.http.'
                   'util.get_real_ip',
                   return_value=ip_address(remote_addr)):
            resp = yield from mock_api_client.get(
                const.URL_API, params={'api_password': ''})

            assert resp.status == 401, \
                "{} shouldn't be trusted".format(remote_addr)


@asyncio.coroutine
def test_access_with_password_in_header(mock_api_client, caplog):
    """Test access with password in URL."""
    # Hide logging from requests package that we use to test logging
    req = yield from mock_api_client.get(
        const.URL_API, headers={const.HTTP_HEADER_HA_AUTH: API_PASSWORD})

    assert req.status == 200

    logs = caplog.text

    assert const.URL_API in logs
    assert API_PASSWORD not in logs


@asyncio.coroutine
def test_access_denied_with_wrong_password_in_url(mock_api_client):
    """Test access with wrong password."""
    resp = yield from mock_api_client.get(
        const.URL_API, params={'api_password': 'wrongpassword'})

    assert resp.status == 401


@asyncio.coroutine
def test_access_with_password_in_url(mock_api_client, caplog):
    """Test access with password in URL."""
    req = yield from mock_api_client.get(
        const.URL_API, params={'api_password': API_PASSWORD})

    assert req.status == 200

    logs = caplog.text

    assert const.URL_API in logs
    assert API_PASSWORD not in logs


@asyncio.coroutine
def test_access_granted_with_x_forwarded_for(hass, mock_api_client, caplog,
                                             mock_trusted_networks):
    """Test access denied through the X-Forwarded-For http header."""
    hass.http.app[KEY_USE_X_FORWARDED_FOR] = True
    for remote_addr in TRUSTED_ADDRESSES:
        resp = yield from mock_api_client.get(const.URL_API, headers={
            HTTP_HEADER_X_FORWARDED_FOR: remote_addr})

        assert resp.status == 200, \
            "{} should be trusted".format(remote_addr)


@asyncio.coroutine
def test_access_granted_with_trusted_ip(mock_api_client, caplog,
                                        mock_trusted_networks):
    """Test access with trusted addresses."""
    for remote_addr in TRUSTED_ADDRESSES:
        with patch('homeassistant.components.http.'
                   'auth.get_real_ip',
                   return_value=ip_address(remote_addr)):
            resp = yield from mock_api_client.get(
                const.URL_API, params={'api_password': ''})

            assert resp.status == 200, \
                '{} should be trusted'.format(remote_addr)
