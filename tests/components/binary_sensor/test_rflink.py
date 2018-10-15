"""Test for RFlink sensor components.

Test setup of rflink sensor component/platform. Verify manual and
automatic sensor creation.

"""

import asyncio
from datetime import timedelta

from ..test_rflink import mock_rflink
from homeassistant.components.rflink import (
    CONF_RECONNECT_INTERVAL)

import homeassistant.core as ha
from homeassistant.const import (
    EVENT_STATE_CHANGED, STATE_ON, STATE_OFF, STATE_UNAVAILABLE)
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

DOMAIN = 'binary_sensor'

CONFIG = {
    'rflink': {
        'port': '/dev/ttyABC0',
        'ignore_devices': ['ignore_wildcard_*', 'ignore_sensor'],
    },
    DOMAIN: {
        'platform': 'rflink',
        'devices': {
            'test': {
                'name': 'test',
                'device_class': 'door',
            },
            'test2': {
                'name': 'test2',
                'device_class': 'motion',
                'off_delay': 30,
                'force_update': True,
            },
        },
    },
}


@asyncio.coroutine
def test_default_setup(hass, monkeypatch):
    """Test all basic functionality of the rflink sensor component."""
    # setup mocking rflink module
    event_callback, create, _, disconnect_callback = yield from mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch)

    # make sure arguments are passed
    assert create.call_args_list[0][1]['ignore']

    # test default state of sensor loaded from config
    config_sensor = hass.states.get('binary_sensor.test')
    assert config_sensor
    assert config_sensor.state == STATE_OFF
    assert config_sensor.attributes['device_class'] == 'door'

    # test event for config sensor
    event_callback({
        'id': 'test',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get('binary_sensor.test').state == STATE_ON

    # test event for config sensor
    event_callback({
        'id': 'test',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get('binary_sensor.test').state == STATE_OFF


@asyncio.coroutine
def test_entity_availability(hass, monkeypatch):
    """If Rflink device is disconnected, entities should become unavailable."""
    # Make sure Rflink mock does not 'recover' to quickly from the
    # disconnect or else the unavailability cannot be measured
    config = CONFIG
    failures = [True, True]
    config[CONF_RECONNECT_INTERVAL] = 60

    # Create platform and entities
    event_callback, create, _, disconnect_callback = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch, failures=failures)

    # Entities are available by default
    assert hass.states.get('binary_sensor.test').state == STATE_OFF

    # Mock a disconnect of the Rflink device
    disconnect_callback()

    # Wait for dispatch events to propagate
    yield from hass.async_block_till_done()

    # Entity should be unavailable
    assert hass.states.get('binary_sensor.test').state == STATE_UNAVAILABLE

    # Reconnect the Rflink device
    disconnect_callback()

    # Wait for dispatch events to propagate
    yield from hass.async_block_till_done()

    # Entities should be available again
    assert hass.states.get('binary_sensor.test').state == STATE_OFF


@asyncio.coroutine
def test_off_delay(hass, monkeypatch):
    """Test off_delay option."""
    # setup mocking rflink module
    event_callback, create, _, disconnect_callback = yield from mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch)

    # make sure arguments are passed
    assert create.call_args_list[0][1]['ignore']

    events = []

    @ha.callback
    def callback(event):
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    # turn on sensor
    event_callback({
        'id': 'test2',
        'command': 'on',
    })
    yield from hass.async_block_till_done()
    state = hass.states.get('binary_sensor.test2')
    assert state.state == STATE_ON
    assert len(events) == 1

    # turn on sensor again
    event_callback({
        'id': 'test2',
        'command': 'on',
    })
    yield from hass.async_block_till_done()
    state = hass.states.get('binary_sensor.test2')
    assert state.state == STATE_ON
    assert len(events) == 2

    # fake time change and verify sensor sent a single off event
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    yield from hass.async_block_till_done()
    state = hass.states.get('binary_sensor.test2')
    assert state.state == STATE_OFF
    assert len(events) == 3
