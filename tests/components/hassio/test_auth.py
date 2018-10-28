"""The tests for the hassio component."""
from unittest.mock import patch, Mock

from homeassistant.const import HTTP_HEADER_HA_AUTH
from homeassistant.exceptions import HomeAssistantError

from tests.common import mock_coro, register_auth_provider
from . import API_PASSWORD


async def test_login_success(hass, hassio_client):
    """Test no auth needed for ."""
    await register_auth_provider(hass, {'type': 'homeassistant'})

    with patch('homeassistant.auth.providers.homeassistant.'
               'HassAuthProvider.async_validate_login',
               Mock(return_value=mock_coro())) as mock_login:
        resp = await hassio_client.post(
            '/api/hassio_auth',
            json={
                "username": "test",
                "password": "123456",
                "addon": "samba",
            },
            headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            }
        )

        # Check we got right response
        assert resp.status == 200
        mock_login.assert_called_with("test", "123456")


async def test_login_error(hass, hassio_client):
    """Test no auth needed for error."""
    await register_auth_provider(hass, {'type': 'homeassistant'})

    with patch('homeassistant.auth.providers.homeassistant.'
               'HassAuthProvider.async_validate_login',
               Mock(side_effect=HomeAssistantError())) as mock_login:
        resp = await hassio_client.post(
            '/api/hassio_auth',
            json={
                "username": "test",
                "password": "123456",
                "addon": "samba",
            },
            headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            }
        )

        # Check we got right response
        assert resp.status == 403
        mock_login.assert_called_with("test", "123456")


async def test_login_no_data(hass, hassio_client):
    """Test auth with no data -> error."""
    await register_auth_provider(hass, {'type': 'homeassistant'})

    with patch('homeassistant.auth.providers.homeassistant.'
               'HassAuthProvider.async_validate_login',
               Mock(side_effect=HomeAssistantError())) as mock_login:
        resp = await hassio_client.post(
            '/api/hassio_auth',
            headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            }
        )

        # Check we got right response
        assert resp.status == 400
        assert not mock_login.called


async def test_login_no_username(hass, hassio_client):
    """Test auth with no username in data -> error."""
    await register_auth_provider(hass, {'type': 'homeassistant'})

    with patch('homeassistant.auth.providers.homeassistant.'
               'HassAuthProvider.async_validate_login',
               Mock(side_effect=HomeAssistantError())) as mock_login:
        resp = await hassio_client.post(
            '/api/hassio_auth',
            json={
                "password": "123456",
                "addon": "samba",
            },
            headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            }
        )

        # Check we got right response
        assert resp.status == 400
        assert not mock_login.called


async def test_login_success_extra(hass, hassio_client):
    """Test auth with extra data."""
    await register_auth_provider(hass, {'type': 'homeassistant'})

    with patch('homeassistant.auth.providers.homeassistant.'
               'HassAuthProvider.async_validate_login',
               Mock(return_value=mock_coro())) as mock_login:
        resp = await hassio_client.post(
            '/api/hassio_auth',
            json={
                "username": "test",
                "password": "123456",
                "addon": "samba",
                "path": "/share",
            },
            headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            }
        )

        # Check we got right response
        assert resp.status == 200
        mock_login.assert_called_with("test", "123456")
