"""Test config flow."""
from collections import namedtuple
from unittest.mock import patch

import pytest

from homeassistant.components.esphomelib import config_flow
from tests.common import mock_coro

MockDeviceInfo = namedtuple("DeviceInfo", ["uses_password", "name"])


@pytest.fixture(autouse=True)
def mock_api_connection_error():
    """Mock out the try login method."""
    with patch('aioesphomeapi.client.APIConnectionError',
               new_callable=lambda: OSError) as mock_error:
        yield mock_error


async def test_user_connection_works(hass):
    """Test we can finish a config flow."""
    flow = config_flow.EsphomelibFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)
    assert result['type'] == 'form'

    with patch('aioesphomeapi.client.APIClient') as mock_client:
        def mock_constructor(loop, host, port, password):
            """Fake the client constructor."""
            mock_client.host = host
            mock_client.port = port
            mock_client.password = password
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.start.return_value = mock_coro()
        mock_client.stop.return_value = mock_coro()
        mock_client.device_info.return_value = mock_coro(
            MockDeviceInfo(False, "test"))
        mock_client.connect.return_value = mock_coro()

        result = await flow.async_step_user(user_input={
            'host': '127.0.0.1',
            'port': 80,
        })

    assert result['type'] == 'create_entry'
    assert result['data'] == {
        'host': '127.0.0.1',
        'port': 80,
        'password': ''
    }
    assert result['title'] == 'test'
    assert len(mock_client.start.mock_calls) == 1
    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.stop.mock_calls) == 1
    assert mock_client.host == '127.0.0.1'
    assert mock_client.port == 80
    assert mock_client.password == ''


async def test_user_connection_error(hass, mock_api_connection_error):
    """Test user step with connection error."""
    flow = config_flow.EsphomelibFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    with patch('aioesphomeapi.client.APIClient') as mock_client:
        def mock_constructor(loop, host, port, password):
            """Fake the client constructor."""
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.start.return_value = mock_coro()
        mock_client.stop.return_value = mock_coro()
        mock_client.device_info.side_effect = mock_api_connection_error
        mock_client.connect.return_value = mock_coro()

        result = await flow.async_step_user(user_input={
            'host': '127.0.0.1',
            'port': 6053,
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'user'
    assert result['errors'] == {
        'base': 'connection_error'
    }
    assert len(mock_client.start.mock_calls) == 1
    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.stop.mock_calls) == 1


async def test_user_with_password(hass):
    """Test user step with password."""
    flow = config_flow.EsphomelibFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    with patch('aioesphomeapi.client.APIClient') as mock_client:
        def mock_constructor(loop, host, port, password):
            """Fake the client constructor."""
            mock_client.password = password
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.start.return_value = mock_coro()
        mock_client.stop.return_value = mock_coro()
        mock_client.device_info.return_value = mock_coro(
            MockDeviceInfo(True, "test"))
        mock_client.connect.return_value = mock_coro()
        mock_client.login.return_value = mock_coro()

        result = await flow.async_step_user(user_input={
            'host': '127.0.0.1',
            'port': 6053,
        })

        assert result['type'] == 'form'
        assert result['step_id'] == 'authenticate'

        result = await flow.async_step_authenticate(user_input={
            'password': 'password1'
        })

    assert result['type'] == 'create_entry'
    assert result['data'] == {
        'host': '127.0.0.1',
        'port': 6053,
        'password': 'password1'
    }
    assert mock_client.password == 'password1'


async def test_user_invalid_password(hass, mock_api_connection_error):
    """Test user step with invalid password."""
    flow = config_flow.EsphomelibFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    with patch('aioesphomeapi.client.APIClient') as mock_client:
        def mock_constructor(loop, host, port, password):
            """Fake the client constructor."""
            mock_client.password = password
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.start.return_value = mock_coro()
        mock_client.stop.return_value = mock_coro()
        mock_client.device_info.return_value = mock_coro(
            MockDeviceInfo(True, "test"))
        mock_client.connect.return_value = mock_coro()
        mock_client.login.side_effect = mock_api_connection_error

        await flow.async_step_user(user_input={
            'host': '127.0.0.1',
            'port': 6053,
        })
        result = await flow.async_step_authenticate(user_input={
            'password': 'invalid'
        })

        assert result['type'] == 'form'
        assert result['step_id'] == 'authenticate'
        assert result['errors'] == {
            'base': 'invalid_password'
        }
