"""Test config flow."""
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.esphome import config_flow
from tests.common import mock_coro, MockConfigEntry

MockDeviceInfo = namedtuple("DeviceInfo", ["uses_password", "name"])


@pytest.fixture(autouse=True)
def aioesphomeapi_mock():
    """Mock aioesphomeapi."""
    with patch.dict('sys.modules', {
        'aioesphomeapi': MagicMock(),
    }):
        yield


@pytest.fixture
def mock_client():
    """Mock APIClient."""
    with patch('aioesphomeapi.APIClient') as mock_client:
        def mock_constructor(loop, host, port, password):
            """Fake the client constructor."""
            mock_client.host = host
            mock_client.port = port
            mock_client.password = password
            return mock_client

        mock_client.side_effect = mock_constructor
        mock_client.connect.return_value = mock_coro()
        mock_client.disconnect.return_value = mock_coro()

        yield mock_client


@pytest.fixture(autouse=True)
def mock_api_connection_error():
    """Mock out the try login method."""
    with patch('aioesphomeapi.APIConnectionError',
               new_callable=lambda: OSError) as mock_error:
        yield mock_error


async def test_user_connection_works(hass, mock_client):
    """Test we can finish a config flow."""
    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)
    assert result['type'] == 'form'

    mock_client.device_info.return_value = mock_coro(
        MockDeviceInfo(False, "test"))

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
    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1
    assert mock_client.host == '127.0.0.1'
    assert mock_client.port == 80
    assert mock_client.password == ''


async def test_user_resolve_error(hass, mock_api_connection_error,
                                  mock_client):
    """Test user step with IP resolve error."""
    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    class MockResolveError(mock_api_connection_error):
        """Create an exception with a specific error message."""

        def __init__(self):
            """Initialize."""
            super().__init__("Error resolving IP address")

    with patch('aioesphomeapi.APIConnectionError',
               new_callable=lambda: MockResolveError,
               ) as exc:
        mock_client.device_info.side_effect = exc
        result = await flow.async_step_user(user_input={
            'host': '127.0.0.1',
            'port': 6053,
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'user'
    assert result['errors'] == {
        'base': 'resolve_error'
    }
    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_user_connection_error(hass, mock_api_connection_error,
                                     mock_client):
    """Test user step with connection error."""
    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    mock_client.device_info.side_effect = mock_api_connection_error

    result = await flow.async_step_user(user_input={
        'host': '127.0.0.1',
        'port': 6053,
    })

    assert result['type'] == 'form'
    assert result['step_id'] == 'user'
    assert result['errors'] == {
        'base': 'connection_error'
    }
    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1


async def test_user_with_password(hass, mock_client):
    """Test user step with password."""
    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    mock_client.device_info.return_value = mock_coro(
        MockDeviceInfo(True, "test"))

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


async def test_user_invalid_password(hass, mock_api_connection_error,
                                     mock_client):
    """Test user step with invalid password."""
    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    await flow.async_step_user(user_input=None)

    mock_client.device_info.return_value = mock_coro(
        MockDeviceInfo(True, "test"))

    await flow.async_step_user(user_input={
        'host': '127.0.0.1',
        'port': 6053,
    })
    mock_client.connect.side_effect = mock_api_connection_error
    result = await flow.async_step_authenticate(user_input={
        'password': 'invalid'
    })

    assert result['type'] == 'form'
    assert result['step_id'] == 'authenticate'
    assert result['errors'] == {
        'base': 'invalid_password'
    }


async def test_discovery_initiation(hass, mock_client):
    """Test discovery importing works."""
    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    service_info = {
        'host': '192.168.43.183',
        'port': 6053,
        'hostname': 'test8266.local.',
        'properties': {}
    }

    mock_client.device_info.return_value = mock_coro(
        MockDeviceInfo(False, "test8266"))

    result = await flow.async_step_discovery(user_input=service_info)
    assert result['type'] == 'create_entry'
    assert result['title'] == 'test8266'
    assert result['data']['host'] == 'test8266.local'
    assert result['data']['port'] == 6053


async def test_discovery_already_configured_hostname(hass, mock_client):
    """Test discovery aborts if already configured via hostname."""
    MockConfigEntry(
        domain='esphome',
        data={'host': 'test8266.local', 'port': 6053, 'password': ''}
    ).add_to_hass(hass)

    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    service_info = {
        'host': '192.168.43.183',
        'port': 6053,
        'hostname': 'test8266.local.',
        'properties': {}
    }
    result = await flow.async_step_discovery(user_input=service_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'


async def test_discovery_already_configured_ip(hass, mock_client):
    """Test discovery aborts if already configured via static IP."""
    MockConfigEntry(
        domain='esphome',
        data={'host': '192.168.43.183', 'port': 6053, 'password': ''}
    ).add_to_hass(hass)

    flow = config_flow.EsphomeFlowHandler()
    flow.hass = hass
    service_info = {
        'host': '192.168.43.183',
        'port': 6053,
        'hostname': 'test8266.local.',
        'properties': {}
    }
    result = await flow.async_step_discovery(user_input=service_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'
