"""Test for RFLink cover components.

Test setup of RFLink covers component/platform. State tracking and
control of RFLink cover devices.

"""

import logging

from homeassistant.components.rflink import EVENT_BUTTON_PRESSED
from homeassistant.const import (
    SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER,
    STATE_OPEN, STATE_CLOSED, ATTR_ENTITY_ID)
from homeassistant.core import callback, State, CoreState

from tests.common import mock_restore_cache
from ..test_rflink import mock_rflink

DOMAIN = 'cover'

CONFIG = {
    'rflink': {
        'port': '/dev/ttyABC0',
        'ignore_devices': ['ignore_wildcard_*', 'ignore_cover'],
    },
    DOMAIN: {
        'platform': 'rflink',
        'devices': {
            'protocol_0_0': {
                'name': 'test',
                'aliases': ['test_alias_0_0'],
            },
            'cover_0_0': {
                'name': 'dim_test',
            },
            'cover_0_1': {
                'name': 'cover_test',
            }
        },
    },
}

_LOGGER = logging.getLogger(__name__)


async def test_default_setup(hass, monkeypatch):
    """Test all basic functionality of the RFLink cover component."""
    # setup mocking rflink module
    event_callback, create, protocol, _ = await mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch)

    # make sure arguments are passed
    assert create.call_args_list[0][1]['ignore']

    # test default state of cover loaded from config
    cover_initial = hass.states.get(DOMAIN + '.test')
    assert cover_initial.state == STATE_CLOSED
    assert cover_initial.attributes['assumed_state']

    # cover should follow state of the hardware device by interpreting
    # incoming events for its name and aliases

    # mock incoming command event for this device
    event_callback({
        'id': 'protocol_0_0',
        'command': 'up',
    })
    await hass.async_block_till_done()

    cover_after_first_command = hass.states.get(DOMAIN + '.test')
    assert cover_after_first_command.state == STATE_OPEN
    # not sure why, but cover have always assumed_state=true
    assert cover_after_first_command.attributes.get('assumed_state')

    # mock incoming command event for this device
    event_callback({
        'id': 'protocol_0_0',
        'command': 'down',
    })
    await hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # should respond to group command
    event_callback({
        'id': 'protocol_0_0',
        'command': 'allon',
    })
    await hass.async_block_till_done()

    cover_after_first_command = hass.states.get(DOMAIN + '.test')
    assert cover_after_first_command.state == STATE_OPEN

    # should respond to group command
    event_callback({
        'id': 'protocol_0_0',
        'command': 'alloff',
    })
    await hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # test following aliases
    # mock incoming command event for this device alias
    event_callback({
        'id': 'test_alias_0_0',
        'command': 'up',
    })
    await hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == STATE_OPEN

    # test changing state from HA propagates to RFLink
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_CLOSE_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    await hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED
    assert protocol.send_command_ack.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[0][0][1] == 'DOWN'

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_OPEN_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    await hass.async_block_till_done()
    assert hass.states.get(DOMAIN + '.test').state == STATE_OPEN
    assert protocol.send_command_ack.call_args_list[1][0][1] == 'UP'


async def test_firing_bus_event(hass, monkeypatch):
    """Incoming RFLink command events should be put on the HA event bus."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'aliases': ['test_alias_0_0'],
                    'fire_event': True,
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    calls = []

    @callback
    def listener(event):
        calls.append(event)
    hass.bus.async_listen_once(EVENT_BUTTON_PRESSED, listener)

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol_0_0',
        'command': 'down',
    })
    await hass.async_block_till_done()

    assert calls[0].data == {'state': 'down', 'entity_id': DOMAIN + '.test'}


async def test_signal_repetitions(hass, monkeypatch):
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
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test if signal repetition is performed according to configuration
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_OPEN_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))

    # wait for commands and repetitions to finish
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 2

    # test if default apply to configured devices
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_OPEN_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test1'}))

    # wait for commands and repetitions to finish
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 5


async def test_signal_repetitions_alternation(hass, monkeypatch):
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
    _, _, protocol, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_CLOSE_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_CLOSE_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test1'}))

    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[1][0][0] == 'protocol_0_1'
    assert protocol.send_command_ack.call_args_list[2][0][0] == 'protocol_0_0'
    assert protocol.send_command_ack.call_args_list[3][0][0] == 'protocol_0_1'


async def test_signal_repetitions_cancelling(hass, monkeypatch):
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
    _, _, protocol, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_CLOSE_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_OPEN_COVER,
                                 {ATTR_ENTITY_ID: DOMAIN + '.test'}))

    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[0][0][1] == 'DOWN'
    assert protocol.send_command_ack.call_args_list[1][0][1] == 'UP'
    assert protocol.send_command_ack.call_args_list[2][0][1] == 'UP'
    assert protocol.send_command_ack.call_args_list[3][0][1] == 'UP'


async def test_group_alias(hass, monkeypatch):
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
                    'group_aliases': ['test_group_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # test sending group command to group alias
    event_callback({
        'id': 'test_group_0_0',
        'command': 'allon',
    })
    await hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == STATE_OPEN

    # test sending group command to group alias
    event_callback({
        'id': 'test_group_0_0',
        'command': 'down',
    })
    await hass.async_block_till_done()

    assert hass.states.get(DOMAIN + '.test').state == STATE_OPEN


async def test_nogroup_alias(hass, monkeypatch):
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
                    'nogroup_aliases': ['test_nogroup_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # test sending group command to nogroup alias
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'allon',
    })
    await hass.async_block_till_done()
    # should not affect state
    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # test sending group command to nogroup alias
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'up',
    })
    await hass.async_block_till_done()
    # should affect state
    assert hass.states.get(DOMAIN + '.test').state == STATE_OPEN


async def test_nogroup_device_id(hass, monkeypatch):
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
    event_callback, _, _, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # test sending group command to nogroup
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'allon',
    })
    await hass.async_block_till_done()
    # should not affect state
    assert hass.states.get(DOMAIN + '.test').state == STATE_CLOSED

    # test sending group command to nogroup
    event_callback({
        'id': 'test_nogroup_0_0',
        'command': 'up',
    })
    await hass.async_block_till_done()
    # should affect state
    assert hass.states.get(DOMAIN + '.test').state == STATE_OPEN


async def test_disable_automatic_add(hass, monkeypatch):
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
    event_callback, _, _, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({
        'id': 'protocol_0_0',
        'command': 'down',
    })
    await hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get(DOMAIN + '.protocol_0_0')


async def test_restore_state(hass, monkeypatch):
    """Ensure states are restored on startup."""
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        DOMAIN: {
            'platform': 'rflink',
            'devices': {
                'RTS_12345678_0': {
                    'name': 'c1',
                },
                'test_restore_2': {
                    'name': 'c2',
                },
                'test_restore_3': {
                    'name': 'c3',
                },
                'test_restore_4': {
                    'name': 'c4',
                },
            },
        },
    }

    mock_restore_cache(hass, (
        State(DOMAIN + '.c1', STATE_OPEN, ),
        State(DOMAIN + '.c2', STATE_CLOSED, ),
    ))

    hass.state = CoreState.starting

    # setup mocking rflink module
    _, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    state = hass.states.get(DOMAIN + '.c1')
    assert state
    assert state.state == STATE_OPEN

    state = hass.states.get(DOMAIN + '.c2')
    assert state
    assert state.state == STATE_CLOSED

    state = hass.states.get(DOMAIN + '.c3')
    assert state
    assert state.state == STATE_CLOSED

    # not cached cover must default values
    state = hass.states.get(DOMAIN + '.c4')
    assert state
    assert state.state == STATE_CLOSED
    assert state.attributes['assumed_state']
