"""Common functions for Rflink component tests and generic platform tests."""

import asyncio
from unittest.mock import Mock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.rflink import CONF_RECONNECT_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from tests.common import assert_setup_component


@asyncio.coroutine
def mock_rflink(hass, config, domain, monkeypatch):
    """Create mock Rflink asyncio protocol, test component setup."""
    transport, protocol = (Mock(), Mock())

    @asyncio.coroutine
    def send_command_ack(*command):
        return True
    protocol.send_command_ack = Mock(wraps=send_command_ack)

    @asyncio.coroutine
    def send_command(*command):
        return True
    protocol.send_command = Mock(wraps=send_command)

    @asyncio.coroutine
    def create_rflink_connection(*args, **kwargs):
        """Return mocked transport and protocol."""
        return transport, protocol
    mock_create = Mock(wraps=create_rflink_connection)
    monkeypatch.setattr(
        'rflink.protocol.create_rflink_connection',
        mock_create)

    # verify instanstiation of component with given config
    with assert_setup_component(1, domain):
        yield from async_setup_component(hass, domain, config)

    # hook into mock config for injecting events
    event_callback = mock_create.call_args_list[0][1]['event_callback']
    assert event_callback

    print(mock_create.call_args_list)
    disconnect_callback = mock_create.call_args_list[
        0][1]['disconnect_callback']
    print(disconnect_callback)

    return event_callback, mock_create, protocol, disconnect_callback


@asyncio.coroutine
def test_version_banner(hass, monkeypatch):
    """Test sending unknown commands doesn't cause issues."""
    # use sensor domain during testing main platform
    domain = 'sensor'
    config = {
        'rflink': {'port': '/dev/ttyABC0', },
        domain: {
            'platform': 'rflink',
            'devices': {
                'test': {'name': 'test', 'sensor_type': 'temperature', },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
        hass, config, domain, monkeypatch)

    event_callback({
        'hardware': 'Nodo RadioFrequencyLink',
        'firmware': 'RFLink Gateway',
        'version': '1.1',
        'revision': '45',
    })


@asyncio.coroutine
def test_send_no_wait(hass, monkeypatch):
    """Test command sending without ack."""
    domain = 'switch'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            'wait_for_ack': False,
        },
        domain: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                        'name': 'test',
                        'aliasses': ['test_alias_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = yield from mock_rflink(
        hass, config, domain, monkeypatch)

    hass.async_add_job(
        hass.services.async_call(domain, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: 'switch.test'}))
    yield from hass.async_block_till_done()
    assert protocol.send_command.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command.call_args_list[0][0][1] == 'off'


@asyncio.coroutine
def test_reconnecting(hass, monkeypatch):
    """An unexpected disconnect should cause a reconnect."""
    domain = 'sensor'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            CONF_RECONNECT_INTERVAL: 0,
        },
        domain: {
            'platform': 'rflink',
        },
    }

    # setup mocking rflink module
    _, _, _, disconnect_callback = yield from mock_rflink(
        hass, config, domain, monkeypatch)

    assert disconnect_callback

    disconnect_callback(None)
