"""Test config flow."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_coro, MockConfigEntry


@pytest.fixture(autouse=True)
def mock_finish_setup():
    """Mock out the finish setup method."""
    with patch('homeassistant.components.mqtt.MQTT.async_connect',
               return_value=mock_coro(True)) as mock_finish:
        yield mock_finish


@pytest.fixture
def mock_try_connection():
    """Mock the try connection method."""
    with patch(
        'homeassistant.components.mqtt.config_flow.try_connection'
    ) as mock_try:
        yield mock_try


async def test_user_connection_works(hass, mock_try_connection,
                                     mock_finish_setup):
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        'mqtt', context={'source': 'user'})
    assert result['type'] == 'form'

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'broker': '127.0.0.1',
        }
    )

    assert result['type'] == 'create_entry'
    assert result['result'].data == {
        'broker': '127.0.0.1',
        'port': 1883,
        'discovery': False,
    }
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


async def test_user_connection_fails(hass, mock_try_connection,
                                     mock_finish_setup):
    """Test if connnection cannot be made."""
    mock_try_connection.return_value = False

    result = await hass.config_entries.flow.async_init(
        'mqtt', context={'source': 'user'})
    assert result['type'] == 'form'

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'broker': '127.0.0.1',
        }
    )

    assert result['type'] == 'form'
    assert result['errors']['base'] == 'cannot_connect'

    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry did not setup
    assert len(mock_finish_setup.mock_calls) == 0


async def test_manual_config_set(hass, mock_try_connection,
                                 mock_finish_setup):
    """Test we ignore entry if manual config available."""
    assert await async_setup_component(
        hass, 'mqtt', {'mqtt': {'broker': 'bla'}})
    assert len(mock_finish_setup.mock_calls) == 1

    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        'mqtt', context={'source': 'user'})
    assert result['type'] == 'abort'


async def test_user_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain='mqtt').add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        'mqtt', context={'source': 'user'})
    assert result['type'] == 'abort'
    assert result['reason'] == 'single_instance_allowed'


async def test_hassio_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain='mqtt').add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        'mqtt', context={'source': 'hassio'})
    assert result['type'] == 'abort'
    assert result['reason'] == 'single_instance_allowed'


async def test_hassio_confirm(hass, mock_try_connection,
                              mock_finish_setup):
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        'mqtt',
        data={
            'addon': 'Mock Addon',
            'broker': 'mock-broker',
            'port': 1883,
            'username': 'mock-user',
            'password': 'mock-pass',
            'protocol': '3.1.1'
        },
        context={'source': 'hassio'}
    )
    assert result['type'] == 'form'
    assert result['step_id'] == 'hassio_confirm'
    assert result['description_placeholders'] == {
        'addon': 'Mock Addon',
    }

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'discovery': True,
        }
    )

    assert result['type'] == 'create_entry'
    assert result['result'].data == {
        'broker': 'mock-broker',
        'port': 1883,
        'username': 'mock-user',
        'password': 'mock-pass',
        'protocol': '3.1.1',
        'discovery': True,
    }
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1
