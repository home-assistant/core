"""Test for IOBL light components.

Test setup of IOBL lights component/platform. State tracking and
control of IOBL switch devices.

"""

import asyncio

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.legrandinone import EVENT_BUTTON_PRESSED
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.core import callback

from ..test_legrandinone import mock_legrandinone

DOMAIN = 'light'

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
            234567: {
                'name': 'dim_test',
                'type': 'dimmable',
            },
            345678: {
                'name': 'switch_test',
                'type': 'switchable',
            }
        },
    },
}


@asyncio.coroutine
def test_default_setup(hass, monkeypatch):
    """Test all basic functionality of the IOBL switch component."""
    # setup mocking rflink module
    event_callback, create, protocol, _ = yield from mock_legrandinone(
        hass, CONFIG, DOMAIN, monkeypatch)

    # test default state of light loaded from config
    light_initial = hass.states.get(DOMAIN + '.test')
    assert light_initial.state == 'off'
    assert light_initial.attributes['assumed_state']

    # light should follow state of the hardware device by interpreting
    # incoming events for its name and aliases

    # mock incoming command event for this device
    event_callback({
        'type': 'bus_command',
        'legrand_id': '123456',
        'what': 'on',
    })
    yield from hass.async_block_till_done()

    light_after_first_command = hass.states.get(DOMAIN + '.test')
    assert light_after_first_command.state == 'on'
    # also after receiving first command state not longer has to be assumed
    assert not light_after_first_command.attributes.get('assumed_state')

    # mock incoming command event for this device
    event_callback({
        'type': 'bus_command',
        'legrand_id': '123456',
        'what': 'off',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test event for new unconfigured sensor
    event_callback({
        'type': 'bus_command',
        'legrand_id': '666666',
        'who': 'light',
        'what': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.666666').state == 'on'

    # test changing state from HA propagates to IOBL
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'off'
    assert protocol.send_packet.call_args_list[0][0][0] == {
        'type': 'bus_command',
        'legrand_id': '123456',
        'who': 'light',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '0',
        'what': 'off'
        }

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'on'
    assert protocol.send_packet.call_args_list[1][0][0] == {
        'type': 'bus_command',
        'legrand_id': '123456',
        'who': 'light',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '0',
        'what': 'on'
        }

    # protocols supporting dimming and on/off should create diming light entity
    event_callback({
        'type': 'bus_command',
        'legrand_id': '234567',
        'what': 'off',
    })
    yield from hass.async_block_till_done()
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {
                                     ATTR_ENTITY_ID: DOMAIN + '.dim_test',
                                     ATTR_BRIGHTNESS: 128,
                                 }))
    yield from hass.async_block_till_done()

    assert protocol.send_packet.call_args_list[2][0][0] == {
        'type': 'set_dimension',
        'legrand_id': '234567',
        'who': 'light',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '0',
        'dimension': 'go_to_level_time',
        'values': ['50']
        }

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {
                                     ATTR_ENTITY_ID: DOMAIN + '.dim_test',
                                 }))
    yield from hass.async_block_till_done()

    assert protocol.send_packet.call_args_list[3][0][0] == {
        'type': 'bus_command',
        'legrand_id': '234567',
        'who': 'light',
        'mode': 'unicast',
        'media': 'plc',
        'unit': '0',
        'what': 'on'
        }


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
        'what': 'off',
    })
    yield from hass.async_block_till_done()

    assert calls[0].data == {'state': 'off', 'entity_id': DOMAIN + '.test'}


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
        'what': 'off',
    })
    yield from hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get(DOMAIN + '.123456')
