"""Test Axis component setup process."""
from unittest.mock import Mock, patch

from homeassistant.setup import async_setup_component
from homeassistant.components import axis

from tests.common import mock_coro, MockConfigEntry


async def test_config_passed_to_config_entry(hass):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(axis, 'configured_devices', return_value={}):
        assert await async_setup_component(hass, axis.DOMAIN, {
            axis.DOMAIN: {
                axis.CONF_NAME: {
                    axis.CONF_HOST: '1.2.3.4',
                    axis.CONF_PORT: 80,
                    axis.CONF_INCLUDE: []
                }
            }
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 1


async def test_incomplete_config_fails(hass):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(axis, 'configured_devices', return_value={}):
        assert await async_setup_component(hass, axis.DOMAIN, {
            axis.DOMAIN: {
                axis.CONF_NAME: {}
            }
        }) is False
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_no_config_passed_to_config_entry(hass):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(axis, 'configured_devices', return_value={}):
        assert await async_setup_component(hass, axis.DOMAIN, {
            axis.DOMAIN: {}
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_successful_setup(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(domain=axis.DOMAIN, data={
        'controller': {
            'host': '0.0.0.0',
            'username': 'user',
            'password': 'pass',
            'port': 80,
        },
        'mac': 'mac mock',
        'model_id': 'model',
        'name': 'name',
        'camera': True,
        'events': ['event1'],
        'trigger_time': 0

    })
    entry.add_to_hass(hass)

    with patch.object(axis, 'AxisNetworkDevice') as mock_device:
        mock_device.return_value.async_setup.return_value = mock_coro(True)
        mock_device.return_value.serial = '00:11:22:33:44:55'
        mock_device.return_value.model_id = 'model'
        mock_device.return_value.name = 'name'
        mock_device.return_value.fw_version = '1.2.3'
        mock_device.return_value.product_type = 'product type'
        assert await axis.async_setup_entry(hass, entry) is True

    assert len(mock_device.mock_calls) == 2
    p_hass, p_entry = mock_device.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry


async def test_setup_return_false(hass):
    """Test that a failed setup still stores device."""
    entry = MockConfigEntry(domain=axis.DOMAIN, data={
        'controller': {
            'host': '0.0.0.0',
            'username': 'user',
            'password': 'pass',
            'port': 80,
        },
        'mac': 'mac mock',
        'model_id': 'model',
        'name': 'name',
        'camera': True,
        'events': ['event1'],
        'trigger_time': 0

    })
    entry.add_to_hass(hass)

    with patch.object(axis, 'AxisNetworkDevice') as mock_device:
        mock_device.return_value.async_setup.return_value = mock_coro(False)
        assert await axis.async_setup_entry(hass, entry) is False

    assert 'mac mock' in hass.data[axis.DOMAIN]

