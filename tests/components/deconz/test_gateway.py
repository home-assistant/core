"""Test deCONZ gateway."""
from unittest.mock import Mock, patch

from homeassistant.components.deconz import gateway

from tests.common import mock_coro

ENTRY_CONFIG = {
    "host": "1.2.3.4",
    "port": 80,
    "api_key": "1234567890ABCDEF",
    "bridgeid": "0123456789ABCDEF",
    "allow_clip_sensor": True,
    "allow_deconz_groups": True,
}


async def test_gateway_setup():
    """Successful setup."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.async_add_remote.return_value = Mock()
    api.sensors = {}

    deconz_gateway = gateway.DeconzGateway(hass, entry)

    with patch.object(gateway, 'get_gateway', return_value=mock_coro(api)), \
        patch.object(
            gateway, 'async_dispatcher_connect', return_value=Mock()):
        assert await deconz_gateway.async_setup() is True

    assert deconz_gateway.api is api
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 6
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'binary_sensor')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[1][1] == \
        (entry, 'cover')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[2][1] == \
        (entry, 'light')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[3][1] == \
        (entry, 'scene')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[4][1] == \
        (entry, 'sensor')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[5][1] == \
        (entry, 'switch')
    assert len(api.start.mock_calls) == 1


async def test_gateway_retry():
    """Retry setup."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    deconz_gateway = gateway.DeconzGateway(hass, entry)

    with patch.object(gateway, 'get_gateway', return_value=mock_coro(False)):
        assert await deconz_gateway.async_setup() is False


async def test_connection_status(hass):
    """Make sure that connection status triggers a dispatcher send."""
    entry = Mock()
    entry.data = ENTRY_CONFIG

    deconz_gateway = gateway.DeconzGateway(hass, entry)
    with patch.object(gateway, 'async_dispatcher_send') as mock_dispatch_send:
        deconz_gateway.async_connection_status_callback(True)

        await hass.async_block_till_done()
        assert len(mock_dispatch_send.mock_calls) == 1
        assert len(mock_dispatch_send.mock_calls[0]) == 3


async def test_add_device(hass):
    """Successful retry setup."""
    entry = Mock()
    entry.data = ENTRY_CONFIG

    deconz_gateway = gateway.DeconzGateway(hass, entry)
    with patch.object(gateway, 'async_dispatcher_send') as mock_dispatch_send:
        deconz_gateway.async_add_device_callback('sensor', Mock())

        await hass.async_block_till_done()
        assert len(mock_dispatch_send.mock_calls) == 1
        assert len(mock_dispatch_send.mock_calls[0]) == 3


async def test_add_remote():
    """Successful add remote."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    remote = Mock()
    remote.name = 'name'
    remote.type = 'ZHASwitch'
    remote.register_async_callback = Mock()

    deconz_gateway = gateway.DeconzGateway(hass, entry)
    deconz_gateway.async_add_remote([remote])

    assert len(deconz_gateway.events) == 1


async def test_shutdown():
    """Successful shutdown."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    deconz_gateway = gateway.DeconzGateway(hass, entry)
    deconz_gateway.api = Mock()
    deconz_gateway.shutdown(None)

    assert len(deconz_gateway.api.close.mock_calls) == 1


async def test_reset_cancel_retry():
    """Verify async reset can handle a scheduled retry."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    deconz_gateway = gateway.DeconzGateway(hass, entry)

    with patch.object(gateway, 'get_gateway', return_value=mock_coro(False)):
        assert await deconz_gateway.async_setup() is False

    assert deconz_gateway._cancel_retry_setup is not None

    assert await deconz_gateway.async_reset() is True


async def test_reset_after_successful_setup():
    """Verify that reset works on a setup component."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.async_add_remote.return_value = Mock()
    api.sensors = {}

    deconz_gateway = gateway.DeconzGateway(hass, entry)

    with patch.object(gateway, 'get_gateway', return_value=mock_coro(api)), \
        patch.object(
            gateway, 'async_dispatcher_connect', return_value=Mock()):
        assert await deconz_gateway.async_setup() is True

    listener = Mock()
    deconz_gateway.listeners = [listener]
    event = Mock()
    event.async_will_remove_from_hass = Mock()
    deconz_gateway.events = [event]
    deconz_gateway.deconz_ids = {'key': 'value'}

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    assert await deconz_gateway.async_reset() is True

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 6

    assert len(listener.mock_calls) == 1
    assert len(deconz_gateway.listeners) == 0

    assert len(event.async_will_remove_from_hass.mock_calls) == 1
    assert len(deconz_gateway.events) == 0

    assert len(deconz_gateway.deconz_ids) == 0


async def test_get_gateway(hass):
    """Successful call."""
    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(True)):
        assert await gateway.get_gateway(hass, ENTRY_CONFIG, Mock(), Mock())


async def test_get_gateway_fails(hass):
    """Failed call."""
    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(False)):
        assert await gateway.get_gateway(
            hass, ENTRY_CONFIG, Mock(), Mock()) is False


async def test_create_event():
    """Successfully created a deCONZ event."""
    hass = Mock()
    remote = Mock()
    remote.name = 'Name'

    event = gateway.DeconzEvent(hass, remote)

    assert event._id == 'name'


async def test_update_event():
    """Successfully update a deCONZ event."""
    hass = Mock()
    remote = Mock()
    remote.name = 'Name'

    event = gateway.DeconzEvent(hass, remote)
    event.async_update_callback({'state': True})

    assert len(hass.bus.async_fire.mock_calls) == 1


async def test_remove_event():
    """Successfully update a deCONZ event."""
    hass = Mock()
    remote = Mock()
    remote.name = 'Name'

    event = gateway.DeconzEvent(hass, remote)
    event.async_will_remove_from_hass()

    assert event._device is None
