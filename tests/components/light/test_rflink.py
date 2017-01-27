"""Test for RFlink light components.

Test setup of rflink lights component/platform. State tracking and
control of Rflink switch devices.

"""

import asyncio

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.rflink import EVENT_BUTTON_PRESSED
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.core import callback

from ..test_rflink import mock_rflink

DOMAIN = 'light'

CONFIG = {
    'rflink': {
        'port': '/dev/ttyABC0',
        'ignore_devices': ['ignore_wildcard_*', 'ignore_light'],
    },
    DOMAIN: {
        'platform': 'rflink',
        'devices': {
            'protocol_0_0': {
                'name': 'test',
                'aliasses': ['test_alias_0_0'],
            },
            'dimmable_0_0': {
                'name': 'dim_test',
                'type': 'dimmable',
            },
        },
    },
}


@asyncio.coroutine
def test_default_setup(hass, monkeypatch):
    """Test all basic functionality of the rflink switch component."""
    # setup mocking rflink module
    event_callback, create, protocol = yield from mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch)

    # make sure arguments are passed
    assert create.call_args_list[0][1]['ignore']

    # test default state of light loaded from config
    light_initial = hass.states.get('light.test')
    assert light_initial.state == 'off'
    assert light_initial.attributes['assumed_state']

    # light should follow state of the hardware device by interpreting
    # incoming events for its name and aliasses

    # mock incoming command event for this device
    event_callback({
        'id': 'protocol_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    light_after_first_command = hass.states.get('light.test')
    assert light_after_first_command.state == 'on'
    # also after receiving first command state not longer has to be assumed
    assert 'assumed_state' not in light_after_first_command.attributes

    # mock incoming command event for this device
    event_callback({
        'id': 'protocol_0_0',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get('light.test').state == 'off'

    # test following aliasses
    # mock incoming command event for this device alias
    event_callback({
        'id': 'test_alias_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get('light.test').state == 'on'

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol2_0_1',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get('light.protocol2_0_1').state == 'on'

    # test changing state from HA propagates to Rflink
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: 'light.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get('light.test').state == 'off'
    assert protocol.send_command_ack.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[0][0][1] == 'off'

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {ATTR_ENTITY_ID: 'light.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get('light.test').state == 'on'
    assert protocol.send_command_ack.call_args_list[1][0][1] == 'on'

    # protocols supporting dimming should send dim commands
    # create dimmable entity
    event_callback({
        'id': 'newkaku_0_1',
        'command': 'off',
    })
    yield from hass.async_block_till_done()
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {ATTR_ENTITY_ID: 'light.newkaku_0_1'}))
    yield from hass.async_block_till_done()

    # dimmable should send highest dim level when turning on
    assert protocol.send_command_ack.call_args_list[2][0][1] == '15'
    # and send on command for fallback
    assert protocol.send_command_ack.call_args_list[3][0][1] == 'on'

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {
                                     ATTR_ENTITY_ID: 'light.newkaku_0_1',
                                     ATTR_BRIGHTNESS: 128,
                                 }))
    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[4][0][1] == '7'


@asyncio.coroutine
def test_new_light_group(hass, monkeypatch):
    """New devices should be added to configured group."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'new_devices_group': 'new_rflink_lights',
        },
    }

    # setup mocking rflink module
    event_callback, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol_0_0',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    # make sure new device is added to correct group
    group = hass.states.get('group.new_rflink_lights')
    assert group.attributes.get('entity_id') == ('light.protocol_0_0',)


@asyncio.coroutine
def test_firing_bus_event(hass, monkeypatch):
    """Incoming Rflink command events should be put on the HA event bus."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
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
    event_callback, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    calls = []

    @callback
    def listener(event):
        calls.append(event)
    hass.bus.async_listen_once(EVENT_BUTTON_PRESSED, listener)

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol_0_0',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    assert calls[0].data == {'state': 'off', 'entity_id': 'test'}
