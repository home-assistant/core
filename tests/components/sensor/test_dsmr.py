"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause
Entity to be updated with new values.

"""

import asyncio
from decimal import Decimal
from unittest.mock import Mock

import asynctest
from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor.dsmr import DerivativeDSMREntity
from homeassistant.const import STATE_UNKNOWN
import pytest
from tests.common import assert_setup_component


@pytest.fixture
def mock_connection_factory(monkeypatch):
    """Mock the create functions for serial and TCP Asyncio connections."""
    from dsmr_parser.clients.protocol import DSMRProtocol
    transport = asynctest.Mock(spec=asyncio.Transport)
    protocol = asynctest.Mock(spec=DSMRProtocol)

    @asyncio.coroutine
    def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)
    connection_factory = Mock(wraps=connection_factory)

    # apply the mock to both connection factories
    monkeypatch.setattr(
        'dsmr_parser.clients.protocol.create_dsmr_reader',
        connection_factory)
    monkeypatch.setattr(
        'dsmr_parser.clients.protocol.create_tcp_dsmr_reader',
        connection_factory)

    return connection_factory, transport, protocol


@asyncio.coroutine
def test_default_setup(hass, mock_connection_factory):
    """Test the default setup."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        CURRENT_ELECTRICITY_USAGE,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject

    config = {'platform': 'dsmr'}

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject([
            {'value': Decimal('0.0'), 'unit': 'kWh'}
        ]),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([
            {'value': '0001', 'unit': ''}
        ]),
    }

    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor',
                                         {'sensor': config})

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # make sure entities have been created and return 'unknown' state
    power_consumption = hass.states.get('sensor.power_consumption')
    assert power_consumption.state == 'unknown'
    assert power_consumption.attributes.get('unit_of_measurement') is None

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to update
    yield from asyncio.sleep(0, loop=hass.loop)

    # ensure entities have new state value after incoming telegram
    power_consumption = hass.states.get('sensor.power_consumption')
    assert power_consumption.state == '0.0'
    assert power_consumption.attributes.get('unit_of_measurement') is 'kWh'

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get('sensor.power_tariff')
    assert power_tariff.state == 'low'
    assert power_tariff.attributes.get('unit_of_measurement') == ''


@asyncio.coroutine
def test_derivative():
    """Test calculation of derivative value."""
    from dsmr_parser.objects import MBusObject

    entity = DerivativeDSMREntity('test', '1.0.0')
    yield from entity.async_update()

    assert entity.state == STATE_UNKNOWN, 'initial state not unknown'

    entity.telegram = {
        '1.0.0': MBusObject([
            {'value': 1},
            {'value': 1, 'unit': 'm3'},
        ])
    }
    yield from entity.async_update()

    assert entity.state == STATE_UNKNOWN, \
        'state after first update should still be unknown'

    entity.telegram = {
        '1.0.0': MBusObject([
            {'value': 2},
            {'value': 2, 'unit': 'm3'},
        ])
    }
    yield from entity.async_update()

    assert entity.state == 1, \
        'state should be difference between first and second update'

    assert entity.unit_of_measurement == 'm3/h'


@asyncio.coroutine
def test_tcp(hass, mock_connection_factory):
    """If proper config provided TCP connection should be made."""
    (connection_factory, transport, protocol) = mock_connection_factory

    config = {
        'platform': 'dsmr',
        'host': 'localhost',
        'port': 1234,
    }

    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor',
                                         {'sensor': config})

    assert connection_factory.call_args_list[0][0][0] == 'localhost'
    assert connection_factory.call_args_list[0][0][1] == '1234'


@asyncio.coroutine
def test_connection_errors_retry(hass, monkeypatch, mock_connection_factory):
    """Connection should be retried on error during setup."""
    (connection_factory, transport, protocol) = mock_connection_factory

    config = {
        'platform': 'dsmr',
        'reconnect_interval': 0,
    }

    # override the mock to have it fail the first time
    first_fail_connection_factory = Mock(
        wraps=connection_factory, side_effect=[
            TimeoutError])

    monkeypatch.setattr(
        'dsmr_parser.clients.protocol.create_dsmr_reader',
        first_fail_connection_factory)
    yield from async_setup_component(hass, 'sensor', {'sensor': config})

    # wait for sleep to resolve
    yield from hass.async_block_till_done()
    assert first_fail_connection_factory.call_count == 2, \
        'connecting not retried'


@asyncio.coroutine
def test_reconnect(hass, monkeypatch, mock_connection_factory):
    """If transport disconnects, the connection should be retried."""
    (connection_factory, transport, protocol) = mock_connection_factory
    config = {
        'platform': 'dsmr',
        'reconnect_interval': 0,
    }

    # mock waiting coroutine while connection lasts
    closed = asyncio.Event(loop=hass.loop)
    # Handshake so that `hass.async_block_till_done()` doesn't cycle forever
    closed2 = asyncio.Event(loop=hass.loop)

    @asyncio.coroutine
    def wait_closed():
        yield from closed.wait()
        closed2.set()
        closed.clear()
    protocol.wait_closed = wait_closed

    yield from async_setup_component(hass, 'sensor', {'sensor': config})

    assert connection_factory.call_count == 1

    # indicate disconnect, release wait lock and allow reconnect to happen
    closed.set()
    # wait for lock set to resolve
    yield from closed2.wait()
    closed2.clear()
    assert not closed.is_set()

    closed.set()
    yield from hass.async_block_till_done()

    assert connection_factory.call_count >= 2, \
        'connecting not retried'
