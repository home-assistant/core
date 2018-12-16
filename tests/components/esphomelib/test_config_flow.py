"""Test config flow."""
from collections import namedtuple
from unittest.mock import patch

import pytest

from tests.common import mock_coro

MockDeviceInfo = namedtuple("DeviceInfo", ["uses_password", "name"])


@pytest.fixture()
def mock_fetch_device_info():
    """Mock out the fetch device info method."""
    with patch(
            'homeassistant.components.esphomelib.config_flow.'
            'fetch_device_info') as mock_fetch:
        yield mock_fetch


@pytest.fixture()
def mock_try_login():
    """Mock out the try login method."""
    with patch(
            'homeassistant.components.esphomelib.config_flow.'
            'try_login') as mock_try:
        yield mock_try


async def test_user_connection_works(hass, mock_fetch_device_info):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        'esphomelib', context={'source': 'user'})
    assert result['type'] == 'form'

    mock_ret = (None, MockDeviceInfo(False, "test"))
    mock_fetch_device_info.return_value = mock_coro(mock_ret)

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'host': '127.0.0.1',
            'port': 80
        }
    )

    assert result['type'] == 'create_entry'
    assert result['result'].data == {
        'host': '127.0.0.1',
        'port': 80,
        'password': ''
    }
    assert len(mock_fetch_device_info.mock_calls) == 1
    assert mock_fetch_device_info.mock_calls[0][1][0] == '127.0.0.1'
    assert mock_fetch_device_info.mock_calls[0][1][1] == 80


async def test_user_connection_error(hass, mock_fetch_device_info):
    """Test user step with connection error."""
    result = await hass.config_entries.flow.async_init(
        'esphomelib', context={'source': 'user'})
    assert result['type'] == 'form'

    mock_ret = ('connection_error', None)
    mock_fetch_device_info.return_value = mock_coro(mock_ret)

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'host': '127.0.0.1',
        }
    )

    assert result['type'] == 'form'
    assert result['errors'] == {
        'base': 'connection_error'
    }
    assert len(mock_fetch_device_info.mock_calls) == 1


async def test_user_with_password(hass, mock_fetch_device_info,
                                  mock_try_login):
    """Test user step with password."""
    result = await hass.config_entries.flow.async_init(
        'esphomelib', context={'source': 'user'})
    assert result['type'] == 'form'

    mock_ret = (None, MockDeviceInfo(True, "test"))
    mock_fetch_device_info.return_value = mock_coro(mock_ret)

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'host': '127.0.0.1',
        }
    )

    assert result['type'] == 'form'
    assert result['step_id'] == 'authenticate'
    assert len(mock_fetch_device_info.mock_calls) == 1

    mock_try_login.return_value = mock_coro('invalid_password')
    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'password': 'password1',
        }
    )
    assert result['type'] == 'form'
    assert result['errors'] == {
        'base': 'invalid_password'
    }

    mock_try_login.return_value = mock_coro(None)
    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'password': 'password2',
        }
    )
    assert result['result'].data == {
        'host': '127.0.0.1',
        'port': 6053,
        'password': 'password2'
    }
