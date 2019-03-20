"""Test Axis device."""
from unittest.mock import Mock, patch

import pytest

from tests.common import mock_coro

from homeassistant.components.axis import device, errors

DEVICE_DATA = {
    device.CONF_HOST: '1.2.3.4',
    device.CONF_USERNAME: 'username',
    device.CONF_PASSWORD: 'password',
    device.CONF_PORT: 1234
}

ENTRY_OPTIONS = {
    device.CONF_CAMERA: True,
    device.CONF_EVENTS: ['pir'],
}

ENTRY_CONFIG = {
    device.CONF_DEVICE: DEVICE_DATA,
    device.CONF_MAC: 'mac',
    device.CONF_MODEL: 'model',
    device.CONF_NAME: 'name'
}


async def test_device_setup():
    """Successful setup."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    entry.options = ENTRY_OPTIONS
    api = Mock()

    axis_device = device.AxisNetworkDevice(hass, entry)

    assert axis_device.host == DEVICE_DATA[device.CONF_HOST]
    assert axis_device.model == ENTRY_CONFIG[device.CONF_MODEL]
    assert axis_device.name == ENTRY_CONFIG[device.CONF_NAME]
    assert axis_device.serial == ENTRY_CONFIG[device.CONF_MAC]

    with patch.object(device, 'get_device', return_value=mock_coro(api)):
        assert await axis_device.async_setup() is True

    assert axis_device.api is api
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 2
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'camera')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[1][1] == \
        (entry, 'binary_sensor')


async def test_device_not_accessible():
    """Failed setup schedules a retry of setup."""
    hass = Mock()
    hass.data = dict()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    entry.options = ENTRY_OPTIONS

    axis_device = device.AxisNetworkDevice(hass, entry)

    with patch.object(device, 'get_device',
                      side_effect=errors.CannotConnect), \
            pytest.raises(device.ConfigEntryNotReady):
        await axis_device.async_setup()

    assert not hass.helpers.event.async_call_later.mock_calls


async def test_device_unknown_error():
    """Unknown errors are handled."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    entry.options = ENTRY_OPTIONS

    axis_device = device.AxisNetworkDevice(hass, entry)

    with patch.object(device, 'get_device', side_effect=Exception):
        assert await axis_device.async_setup() is False

    assert not hass.helpers.event.async_call_later.mock_calls


async def test_new_event_sends_signal(hass):
    """Make sure that new event send signal."""
    entry = Mock()
    entry.data = ENTRY_CONFIG

    axis_device = device.AxisNetworkDevice(hass, entry)

    with patch.object(device, 'async_dispatcher_send') as mock_dispatch_send:
        axis_device.async_signal_callback(action='add', event='event')
        await hass.async_block_till_done()

    assert len(mock_dispatch_send.mock_calls) == 1
    assert len(mock_dispatch_send.mock_calls[0]) == 3


async def test_shutdown():
    """Successful shutdown."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    axis_device = device.AxisNetworkDevice(hass, entry)
    axis_device.api = Mock()

    axis_device.shutdown(None)

    assert len(axis_device.api.stop.mock_calls) == 1


async def test_get_device(hass):
    """Successful call."""
    with patch('axis.vapix.Vapix.load_params',
               return_value=mock_coro()):
        assert await device.get_device(hass, DEVICE_DATA)


async def test_get_device_fails(hass):
    """Device unauthorized yields authentication required error."""
    import axis

    with patch('axis.vapix.Vapix.load_params',
               side_effect=axis.Unauthorized), \
            pytest.raises(errors.AuthenticationRequired):
        await device.get_device(hass, DEVICE_DATA)


async def test_get_device_device_unavailable(hass):
    """Device unavailable yields cannot connect error."""
    import axis

    with patch('axis.vapix.Vapix.load_params',
               side_effect=axis.RequestError), \
            pytest.raises(errors.CannotConnect):
        await device.get_device(hass, DEVICE_DATA)


async def test_get_device_unknown_error(hass):
    """Device yield unknown error."""
    import axis

    with patch('axis.vapix.Vapix.load_params',
               side_effect=axis.AxisException), \
            pytest.raises(errors.AuthenticationRequired):
        await device.get_device(hass, DEVICE_DATA)
