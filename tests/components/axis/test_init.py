"""Test Axis component setup process."""
from unittest.mock import Mock, patch

from homeassistant.setup import async_setup_component
from homeassistant.components import axis

from tests.common import mock_coro, MockConfigEntry


async def test_setup(hass):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(axis, 'configured_devices', return_value={}):

        assert await async_setup_component(hass, axis.DOMAIN, {
            axis.DOMAIN: {
                'device_name': {
                    axis.CONF_HOST: '1.2.3.4',
                    axis.config_flow.CONF_PORT: 80,
                }
            }
        })

    assert len(mock_config_entries.flow.mock_calls) == 1


async def test_setup_device_already_configured(hass):
    """Test already configured device does not configure a second."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(axis, 'configured_devices', return_value={'1.2.3.4'}):

        assert await async_setup_component(hass, axis.DOMAIN, {
            axis.DOMAIN: {
                'device_name': {
                    axis.CONF_HOST: '1.2.3.4'
                }
            }
        })

    assert not mock_config_entries.flow.mock_calls


async def test_setup_no_config(hass):
    """Test setup without configuration."""
    assert await async_setup_component(hass, axis.DOMAIN, {})
    assert axis.DOMAIN not in hass.data


async def test_setup_entry(hass):
    """Test successful setup of entry."""
    entry = MockConfigEntry(
        domain=axis.DOMAIN, data={axis.device.CONF_MAC: '0123'})

    mock_device = Mock()
    mock_device.async_setup.return_value = mock_coro(True)
    mock_device.async_update_device_registry.return_value = mock_coro(True)
    mock_device.serial.return_value = '1'

    with patch.object(axis, 'AxisNetworkDevice') as mock_device_class, \
            patch.object(
                axis, 'async_populate_options', return_value=mock_coro(True)):
        mock_device_class.return_value = mock_device

        assert await axis.async_setup_entry(hass, entry)

    assert len(hass.data[axis.DOMAIN]) == 1


async def test_setup_entry_fails(hass):
    """Test successful setup of entry."""
    entry = MockConfigEntry(
        domain=axis.DOMAIN, data={axis.device.CONF_MAC: '0123'}, options=True)

    mock_device = Mock()
    mock_device.async_setup.return_value = mock_coro(False)

    with patch.object(axis, 'AxisNetworkDevice') as mock_device_class:
        mock_device_class.return_value = mock_device

        assert not await axis.async_setup_entry(hass, entry)

    assert not hass.data[axis.DOMAIN]


async def test_populate_options(hass):
    """Test successful populate options."""
    entry = MockConfigEntry(domain=axis.DOMAIN, data={'device': {}})
    entry.add_to_hass(hass)

    with patch.object(axis, 'get_device', return_value=mock_coro(Mock())):

        await axis.async_populate_options(hass, entry)

    assert entry.options == {
        axis.CONF_CAMERA: True,
        axis.CONF_EVENTS: True,
        axis.CONF_TRIGGER_TIME: axis.DEFAULT_TRIGGER_TIME
    }
