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
            'switchable_0_0': {
                'name': 'switch_test',
                'type': 'switchable',
            }
        },
    },
}


@asyncio.coroutine
def test_default_setup(hass, monkeypatch):
    """Test all basic functionality of the rflink switch component."""
    # setup mocking rflink module
    event_callback, create, protocol, _ = yield from mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch)

    # make sure arguments are passed
    assert create.call_args_list[0][1]['ignore']

    # test default state of light loaded from config
    light_initial = hass.states.get(DOMAIN + '.test')
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

    light_after_first_command = hass.states.get(DOMAIN + '.test')
    assert light_after_first_command.state == 'on'
    # also after receiving first command state not longer has to be assumed
    assert 'assumed_state' not in light_after_first_command.attributes

    # mock incoming command event for this device
    event_callback({
        'id': 'protocol_0_0',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # should repond to group command
    event_callback({
        'id': 'protocol_0_0',
        'command': 'allon',
    })
    yield from hass.async_block_till_done()

    light_after_first_command = hass.states.get(DOMAIN + '.test')
    assert light_after_first_command.state == 'on'

    # should repond to group command
    event_callback({
        'id': 'protocol_0_0',
        'command': 'alloff',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test following aliasses
    # mock incoming command event for this device alias
    event_callback({
        'id': 'test_alias_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == 'on'

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol2_0_1',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.protocol2_0_1').state == 'on'

    # test changing state from HA propagates to Rflink
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'off'
    assert protocol.send_command_ack.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[0][0][1] == 'off'

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    yield from hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == 'on'
    assert protocol.send_command_ack.call_args_list[1][0][1] == 'on'

    # protocols supporting dimming and on/off should create hybrid light entity
    event_callback({
        'id': 'newkaku_0_1',
        'command': 'off',
    })
    yield from hass.async_block_till_done()
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {ATTR_ENTITY_ID: DOMAIN + '.newkaku_0_1'}))
    yield from hass.async_block_till_done()

    # dimmable should send highest dim level when turning on
    assert protocol.send_command_ack.call_args_list[2][0][1] == '15'

    # and send on command for fallback
    assert protocol.send_command_ack.call_args_list[3][0][1] == 'on'

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {
                                     ATTR_ENTITY_ID: DOMAIN + '.newkaku_0_1',
                                     ATTR_BRIGHTNESS: 128,
                                 }))
    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[4][0][1] == '7'

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {
                                     ATTR_ENTITY_ID: DOMAIN + '.dim_test',
                                     ATTR_BRIGHTNESS: 128,
                                 }))
    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[5][0][1] == '7'


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
                    'fire_event': True,
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
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

    assert calls[0].data == {'state': 'off', 'entity_id': DOMAIN + '.test'}


@asyncio.coroutine
def test_signal_repetitions(hass, monkeypatch):
    """Command should be sent amount of configured repetitions."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'device_defaults': {
                'signal_repetitions': 3,
            },
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'signal_repetitions': 2,
                },
                'protocol_0_1': {
                    'name': 'test1',
                },
                'newkaku_0_1': {
                    'type': 'hybrid',
                }
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, protocol, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    # test if signal repetition is performed according to configuration
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))

    # wait for commands and repetitions to finish
    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 2

    # test if default apply to configured devcies
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test1'}))

    # wait for commands and repetitions to finish
    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 5

    # test if device defaults apply to newly created devices
    event_callback({
        'id': 'protocol_0_2',
        'command': 'off',
    })

    # make sure entity is created before setting state
    yield from hass.async_block_till_done()

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.protocol_0_2'}))

    # wait for commands and repetitions to finish
    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 8


@asyncio.coroutine
def test_signal_repetitions_alternation(hass, monkeypatch):
    """Simultaneously switching entities must alternate repetitions."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'signal_repetitions': 2,
                },
                'protocol_0_1': {
                    'name': 'test1',
                    'signal_repetitions': 2,
                },
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test1'}))

    yield from hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[1][0][0] == 'protocol_0_1'
    assert protocol.send_command_ack.call_args_list[2][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[3][0][0] == 'protocol_0_1'


@asyncio.coroutine
def test_signal_repetitions_cancelling(hass, monkeypatch):
    """Cancel outstanding repetitions when state changed."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'signal_repetitions': 3,
                },
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))

    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_ON,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))

    yield from hass.async_block_till_done()

    print(protocol.send_command_ack.call_args_list)
    assert protocol.send_command_ack.call_args_list[0][0][1] == 'off'
    assert protocol.send_command_ack.call_args_list[1][0][1] == 'on'
    assert protocol.send_command_ack.call_args_list[2][0][1] == 'on'
    assert protocol.send_command_ack.call_args_list[3][0][1] == 'on'


@asyncio.coroutine
def test_type_toggle(hass, monkeypatch):
    """Test toggle type lights (on/on)."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'toggle_0_0': {
                    'name': 'toggle_test',
                    'type': 'toggle',
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.toggle_test').state == 'off'

    # test sending on command to toggle alias
    event_callback({
        'id': 'toggle_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.toggle_test').state == 'on'

    # test sending group command to group alias
    event_callback({
        'id': 'toggle_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.toggle_test').state == 'off'


@asyncio.coroutine
def test_group_alias(hass, monkeypatch):
    """Group aliases should only respond to group commands (allon/alloff)."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'group_aliasses': ['test_group_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test sending group command to group alias
    event_callback({
        'id': 'test_group_0_0',
        'command': 'allon',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == 'on'

    # test sending group command to group alias
    event_callback({
        'id': 'test_group_0_0',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == 'on'


@asyncio.coroutine
def test_nogroup_alias(hass, monkeypatch):
    """Non group aliases should not respond to group commands."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'nogroup_aliasses': ['test_nogroup_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test sending group command to nogroup alias
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'allon',
    })
    yield from hass.async_block_till_done()
    # should not affect state
    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test sending group command to nogroup alias
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()
    # should affect state
    assert hass.states.get(DOMAIN + '.test').state == 'on'


@asyncio.coroutine
def test_nogroup_device_id(hass, monkeypatch):
    """Device id that do not respond to group commands (allon/alloff)."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'test_nogroup_0_0': {
                    'name': 'test',
                    'group': False,
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test sending group command to nogroup
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'allon',
    })
    yield from hass.async_block_till_done()
    # should not affect state
    assert hass.states.get(DOMAIN + '.test').state == 'off'

    # test sending group command to nogroup
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'on',
    })
    yield from hass.async_block_till_done()
    # should affect state
    assert hass.states.get(DOMAIN + '.test').state == 'on'


@asyncio.coroutine
def test_disable_automatic_add(hass, monkeypatch):
    """If disabled new devices should not be automatically added."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'automatic_add': False,
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = yield from mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol_0_0',
        'command': 'off',
    })
    yield from hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get(DOMAIN + '.protocol_0_0')
