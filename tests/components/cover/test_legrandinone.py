"""Test for IOBL cover components.

Test setup of IOBL cover component/platform. State tracking and
control of IOBL cover devices.

"""

import asyncio

from homeassistant.components.cover import (SERVICE_OPEN_COVER,
                                            SERVICE_CLOSE_COVER,
                                            SERVICE_STOP_COVER)
from homeassistant.components.legrandinone import EVENT_BUTTON_PRESSED
from homeassistant.const import (
    ATTR_ENTITY_ID)
from homeassistant.core import callback

from ..test_legrandinone import mock_legrandinone

DOMAIN = 'cover'

CONFIG = {
    'legrandinone': {
        'port': '/dev/ttyABC0',
    },
    DOMAIN: {
        'platform': 'legrandinone',
        'devices': {
            123456: {
                'name': 'test',
            },
        },
    },
}


@asyncio.coroutine
def test_default_setup(hass, monkeypatch):
    """Test all basic functionality of the IOBL cover component."""
    # setup mocking rflink module
    event_callback, create, protocol, _ = yield from mock_legrandinone(
        hass, CONFIG, DOMAIN, monkeypatch)

    # test default state of light loaded from config
    cover_initial = hass.states.get(DOMAIN + '.test')
    assert cover_initial.state == 'closed'

    # light should follow state of the hardware device by interpreting
    # incoming events for its name and aliases

    # mock incoming command event for this device
    event_callback({
        'type': 'bus_command',
        'legrand_id': '123456',
        'what': 'move_up',
    })
    yield from hass.async_block_till_done()

    cover_after_first_command = hass.states.get(DOMAIN + '.test')
    assert cover_after_first_command.state == 'open'

    # test changing state from HA propagates to IOBL
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_CLOSE_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'closed'
    assert protocol.send_packet.call_args_list[0][0][0] == {
        'type': 'bus_command',
        'legrand_id': '123456',
        'who': 'automation',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '2',
        'what': 'move_down'
        }

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_OPEN_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'open'
    assert protocol.send_packet.call_args_list[1][0][0] == {
        'type': 'bus_command',
        'legrand_id': '123456',
        'who': 'automation',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '2',
        'what': 'move_up'
        }

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_STOP_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'open'
    assert protocol.send_packet.call_args_list[2][0][0] == {
        'type': 'bus_command',
        'legrand_id': '123456',
        'who': 'automation',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '2',
        'what': 'move_stop'
        }

    # Automatic add of new devices
    event_callback({
        'type': 'bus_command',
        'legrand_id': '234567',
        'who': 'automation',
        'what': 'move_up',
    })
    yield from hass.async_block_till_done()

    cover_after_first_command = hass.states.get(DOMAIN + '.234567')
    assert cover_after_first_command.state == 'open'


@asyncio.coroutine
def test_unknown_event(hass, monkeypatch):
    """Test command sending."""
    config = {
        'legrandinone': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'legrandinone',
            'automatic_add': True,
        },
    }

    # setup mocking iobl module
    event_callback, _, _, _ = yield from mock_legrandinone(
        hass, config, DOMAIN, monkeypatch)

    # Automatic add of new devices
    event_callback({
        'type': 'dimension_request',
        'legrand_id': '234567',
        'who': 'automation',
        'what': 'status',
    })
    yield from hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get('cover' + '.234567')


@asyncio.coroutine
def test_firing_bus_event(hass, monkeypatch):
    """Incoming iobl command events should be put on the HA event bus."""
    config = {
        'legrandinone': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'legrandinone',
            'devices': {
                '123456': {
                    'name': 'test',
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_legrandinone(
        hass, config, DOMAIN, monkeypatch)

    calls = []

    @callback
    def listener(event):
        calls.append(event)
    hass.bus.async_listen_once(EVENT_BUTTON_PRESSED, listener)

    # test event for firing event
    event_callback({
        'type': 'bus_command',
        'legrand_id': '123456',
        'what': 'move_up',
    })
    yield from hass.async_block_till_done()

    assert calls[0].data == {'state': 'move_up', 'entity_id': DOMAIN + '.test'}


@asyncio.coroutine
def test_disable_automatic_add(hass, monkeypatch):
    """If disabled new devices should not be automatically added."""
    config = {
        'legrandinone': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'legrandinone',
            'automatic_add': False,
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_legrandinone(
        hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({
        'type': 'bus_command',
        'legrand_id': '123456',
        'what': 'move_up',
    })
    yield from hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get(DOMAIN + '.123456')
