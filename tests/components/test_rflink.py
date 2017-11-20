"""Common functions for Rflink component tests and generic platform tests."""

import asyncio
from unittest.mock import Mock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.rflink import (
    CONF_RECONNECT_INTERVAL, SERVICE_SEND_COMMAND)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_STOP_COVER)
from tests.common import assert_setup_component


@asyncio.coroutine
def mock_rflink(hass, config, domain, monkeypatch, failures=None,
                platform_count=1):
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
        # failures can be a list of booleans indicating in which sequence
        # creating a connection should success or fail
        if failures:
            fail = failures.pop()
        else:
            fail = False

        if fail:
            raise ConnectionRefusedError
        else:
            return transport, protocol

    mock_create = Mock(wraps=create_rflink_connection)
    monkeypatch.setattr(
        'rflink.protocol.create_rflink_connection',
        mock_create)

    # verify instanstiation of component with given config
    with assert_setup_component(platform_count, domain):
        yield from async_setup_component(hass, domain, config)

    # hook into mock config for injecting events
    event_callback = mock_create.call_args_list[0][1]['event_callback']
    assert event_callback

    disconnect_callback = mock_create.call_args_list[
        0][1]['disconnect_callback']

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
                        'aliases': ['test_alias_0_0'],
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
def test_cover_send_no_wait(hass, monkeypatch):
    """Test command sending to a cover device without ack."""
    domain = 'cover'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            'wait_for_ack': False,
        },
        domain: {
            'platform': 'rflink',
            'devices': {
                'RTS_0100F2_0': {
                        'name': 'test',
                        'aliases': ['test_alias_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = yield from mock_rflink(
        hass, config, domain, monkeypatch)

    hass.async_add_job(
        hass.services.async_call(domain, SERVICE_STOP_COVER,
                                 {ATTR_ENTITY_ID: 'cover.test'}))
    yield from hass.async_block_till_done()
    assert protocol.send_command.call_args_list[0][0][0] == 'RTS_0100F2_0'
    assert protocol.send_command.call_args_list[0][0][1] == 'STOP'


@asyncio.coroutine
def test_send_command(hass, monkeypatch):
    """Test send_command service."""
    domain = 'rflink'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = yield from mock_rflink(
        hass, config, domain, monkeypatch, platform_count=5)

    hass.async_add_job(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND,
                                 {'device_id': 'newkaku_0000c6c2_1',
                                  'command': 'on'}))
    yield from hass.async_block_till_done()
    assert (protocol.send_command_ack.call_args_list[0][0][0]
            == 'newkaku_0000c6c2_1')
    assert protocol.send_command_ack.call_args_list[0][0][1] == 'on'


@asyncio.coroutine
def test_send_command_invalid_arguments(hass, monkeypatch):
    """Test send_command service."""
    domain = 'rflink'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = yield from mock_rflink(
        hass, config, domain, monkeypatch, platform_count=5)

    # one argument missing
    hass.async_add_job(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND,
                                 {'command': 'on'}))
    hass.async_add_job(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND,
                                 {'device_id': 'newkaku_0000c6c2_1'}))
    # no arguments
    hass.async_add_job(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND, {}))
    yield from hass.async_block_till_done()
    assert protocol.send_command_ack.call_args_list == []


@asyncio.coroutine
def test_reconnecting_after_disconnect(hass, monkeypatch):
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
    _, mock_create, _, disconnect_callback = yield from mock_rflink(
        hass, config, domain, monkeypatch)

    assert disconnect_callback, 'disconnect callback not passed to rflink'

    # rflink initiated disconnect
    disconnect_callback(None)

    yield from hass.async_block_till_done()

    # we expect 2 call, the initial and reconnect
    assert mock_create.call_count == 2


@asyncio.coroutine
def test_reconnecting_after_failure(hass, monkeypatch):
    """A failure to reconnect should be retried."""
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

    # success first time but fail second
    failures = [False, True, False]

    # setup mocking rflink module
    _, mock_create, _, disconnect_callback = yield from mock_rflink(
        hass, config, domain, monkeypatch, failures=failures)

    # rflink initiated disconnect
    disconnect_callback(None)

    # wait for reconnects to have happened
    yield from hass.async_block_till_done()
    yield from hass.async_block_till_done()

    # we expect 3 calls, the initial and 2 reconnects
    assert mock_create.call_count == 3


@asyncio.coroutine
def test_error_when_not_connected(hass, monkeypatch):
    """Sending command should error when not connected."""
    domain = 'switch'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            CONF_RECONNECT_INTERVAL: 0,
        },
        domain: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                        'name': 'test',
                        'aliases': ['test_alias_0_0'],
                },
            },
        },
    }

    # success first time but fail second
    failures = [False, True, False]

    # setup mocking rflink module
    _, mock_create, _, disconnect_callback = yield from mock_rflink(
        hass, config, domain, monkeypatch, failures=failures)

    # rflink initiated disconnect
    disconnect_callback(None)

    yield from asyncio.sleep(0, loop=hass.loop)

    success = yield from hass.services.async_call(
        domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: 'switch.test'})
    assert not success, 'changing state should not succeed when disconnected'
