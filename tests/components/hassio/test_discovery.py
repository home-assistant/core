"""Test config flow."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import mock_coro, MockConfigEntry


async def test_hassio_confirm(hass, mock_mqtt):
    """Test we can finish a config flow."""

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
