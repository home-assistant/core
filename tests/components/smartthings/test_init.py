"""Tests for the SmartThings component init module."""
from unittest.mock import Mock, patch
from uuid import uuid4

from aiohttp import ClientConnectionError, ClientResponseError
from pysmartthings import InstalledAppStatus
import pytest

from homeassistant.components import smartthings
from homeassistant.components.smartthings.const import (
    DATA_BROKERS, DOMAIN, EVENT_BUTTON, SIGNAL_SMARTTHINGS_UPDATE,
    SUPPORTED_PLATFORMS)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import mock_coro


async def test_unrecoverable_api_errors_create_new_flow(
        hass, config_entry, smartthings_mock):
    """
    Test a new config flow is initiated when there are API errors.

    401 (unauthorized): Occurs when the access token is no longer valid.
    403 (forbidden/not found): Occurs when the app or installed app could
        not be retrieved/found (likely deleted?)
    """
    api = smartthings_mock.return_value
    for error_status in (401, 403):
        setattr(hass.config_entries, '_entries', [config_entry])
        api.app.return_value = mock_coro(
            exception=ClientResponseError(None, None,
                                          status=error_status))

        # Assert setup returns false
        result = await smartthings.async_setup_entry(hass, config_entry)
        assert not result

        # Assert entry was removed and new flow created
        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)
        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert flows[0]['handler'] == 'smartthings'
        assert flows[0]['context'] == {'source': 'import'}
        hass.config_entries.flow.async_abort(flows[0]['flow_id'])


async def test_recoverable_api_errors_raise_not_ready(
        hass, config_entry, smartthings_mock):
    """Test config entry not ready raised for recoverable API errors."""
    setattr(hass.config_entries, '_entries', [config_entry])
    api = smartthings_mock.return_value
    api.app.return_value = mock_coro(
        exception=ClientResponseError(None, None, status=500))

    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_connection_errors_raise_not_ready(
        hass, config_entry, smartthings_mock):
    """Test config entry not ready raised for connection errors."""
    setattr(hass.config_entries, '_entries', [config_entry])
    api = smartthings_mock.return_value
    api.app.return_value = mock_coro(
        exception=ClientConnectionError())

    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_base_url_no_longer_https_does_not_load(
        hass, config_entry, app, smartthings_mock):
    """Test base_url no longer valid creates a new flow."""
    hass.config.api.base_url = 'http://0.0.0.0'
    setattr(hass.config_entries, '_entries', [config_entry])
    api = smartthings_mock.return_value
    api.app.return_value = mock_coro(return_value=app)

    # Assert setup returns false
    result = await smartthings.async_setup_entry(hass, config_entry)
    assert not result


async def test_unauthorized_installed_app_raises_not_ready(
        hass, config_entry, app, installed_app,
        smartthings_mock):
    """Test config entry not ready raised when the app isn't authorized."""
    setattr(hass.config_entries, '_entries', [config_entry])
    setattr(installed_app, '_installed_app_status',
            InstalledAppStatus.PENDING)

    api = smartthings_mock.return_value
    api.app.return_value = mock_coro(return_value=app)
    api.installed_app.return_value = mock_coro(return_value=installed_app)

    with pytest.raises(ConfigEntryNotReady):
        await smartthings.async_setup_entry(hass, config_entry)


async def test_config_entry_loads_platforms(
        hass, config_entry, app, installed_app,
        device, smartthings_mock):
    """Test config entry loads properly and proxies to platforms."""
    setattr(hass.config_entries, '_entries', [config_entry])

    api = smartthings_mock.return_value
    api.app.return_value = mock_coro(return_value=app)
    api.installed_app.return_value = mock_coro(return_value=installed_app)
    api.devices.return_value = mock_coro(return_value=[device])

    with patch.object(hass.config_entries, 'async_forward_entry_setup',
                      return_value=mock_coro()) as forward_mock:
        assert await smartthings.async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == len(SUPPORTED_PLATFORMS)


async def test_unload_entry(hass, config_entry):
    """Test entries are unloaded correctly."""
    broker = Mock()
    broker.event_handler_disconnect = Mock()
    hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id] = broker

    with patch.object(hass.config_entries, 'async_forward_entry_unload',
                      return_value=mock_coro(
                          return_value=True
                      )) as forward_mock:
        assert await smartthings.async_unload_entry(hass, config_entry)
        assert broker.event_handler_disconnect.call_count == 1
        assert config_entry.entry_id not in hass.data[DOMAIN][DATA_BROKERS]
        # Assert platforms unloaded
        await hass.async_block_till_done()
        assert forward_mock.call_count == len(SUPPORTED_PLATFORMS)


async def test_event_handler_dispatches_updated_devices(
        hass, device_factory, event_request_factory):
    """Test the event handler dispatches updated devices."""
    devices = [
        device_factory('Bedroom 1 Switch', ['switch']),
        device_factory('Bathroom 1', ['switch']),
        device_factory('Sensor', ['motionSensor']),
    ]
    device_ids = [devices[0].device_id, devices[1].device_id,
                  devices[2].device_id]
    request = event_request_factory(device_ids)
    called = False

    def signal(ids):
        nonlocal called
        called = True
        assert device_ids == ids
    async_dispatcher_connect(hass, SIGNAL_SMARTTHINGS_UPDATE, signal)
    broker = smartthings.DeviceBroker(
        hass, devices, request.installed_app_id)

    await broker.event_handler(request, None, None)
    await hass.async_block_till_done()

    assert called
    for device in devices:
        assert device.status.values['Updated'] == 'Value'


async def test_event_handler_ignores_other_installed_app(
        hass, device_factory, event_request_factory):
    """Test the event handler dispatches updated devices."""
    device = device_factory('Bedroom 1 Switch', ['switch'])
    request = event_request_factory([device.device_id])
    called = False

    def signal(ids):
        nonlocal called
        called = True
    async_dispatcher_connect(hass, SIGNAL_SMARTTHINGS_UPDATE, signal)
    broker = smartthings.DeviceBroker(hass, [device], str(uuid4()))

    await broker.event_handler(request, None, None)
    await hass.async_block_till_done()

    assert not called


async def test_event_handler_fires_button_events(
        hass, device_factory, event_factory, event_request_factory):
    """Test the event handler fires button events."""
    device = device_factory('Button 1', ['button'])
    event = event_factory(device.device_id, capability='button',
                          attribute='button', value='pushed')
    request = event_request_factory(events=[event])
    called = False

    def handler(evt):
        nonlocal called
        called = True
        assert evt.data == {
            'component_id': 'main',
            'device_id': device.device_id,
            'location_id': event.location_id,
            'value': 'pushed',
            'name': device.label
        }
    hass.bus.async_listen(EVENT_BUTTON, handler)
    broker = smartthings.DeviceBroker(
        hass, [device], request.installed_app_id)
    await broker.event_handler(request, None, None)
    await hass.async_block_till_done()

    assert called
