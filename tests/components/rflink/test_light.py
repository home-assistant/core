"""Test for RFLink light components.

Test setup of RFLink lights component/platform. State tracking and
control of RFLink switch devices.

"""
import asyncio

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.rflink import EVENT_BUTTON_PRESSED
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import CoreState, HomeAssistant, State, callback

from .test_init import mock_rflink

from tests.common import mock_restore_cache

DOMAIN = "light"

CONFIG = {
    "rflink": {
        "port": "/dev/ttyABC0",
        "ignore_devices": ["ignore_wildcard_*", "ignore_light"],
    },
    DOMAIN: {
        "platform": "rflink",
        "devices": {
            "protocol_0_0": {"name": "test", "aliases": ["test_alias_0_0"]},
            "dimmable_0_0": {"name": "dim_test", "type": "dimmable"},
            "switchable_0_0": {"name": "switch_test", "type": "switchable"},
        },
    },
}


async def test_default_setup(hass: HomeAssistant, monkeypatch) -> None:
    """Test all basic functionality of the RFLink switch component."""
    # setup mocking rflink module
    event_callback, create, protocol, _ = await mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch
    )

    # make sure arguments are passed
    assert create.call_args_list[0][1]["ignore"]

    # test default state of light loaded from config
    light_initial = hass.states.get(f"{DOMAIN}.test")
    assert light_initial.state == "off"
    assert light_initial.attributes["assumed_state"]

    # light should follow state of the hardware device by interpreting
    # incoming events for its name and aliases

    # mock incoming command event for this device
    event_callback({"id": "protocol_0_0", "command": "on"})
    await hass.async_block_till_done()

    light_after_first_command = hass.states.get(f"{DOMAIN}.test")
    assert light_after_first_command.state == "on"
    # also after receiving first command state not longer has to be assumed
    assert not light_after_first_command.attributes.get("assumed_state")

    # mock incoming command event for this device
    event_callback({"id": "protocol_0_0", "command": "off"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # should respond to group command
    event_callback({"id": "protocol_0_0", "command": "allon"})
    await hass.async_block_till_done()

    light_after_first_command = hass.states.get(f"{DOMAIN}.test")
    assert light_after_first_command.state == "on"

    # should respond to group command
    event_callback({"id": "protocol_0_0", "command": "alloff"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # test following aliases
    # mock incoming command event for this device alias
    event_callback({"id": "test_alias_0_0", "command": "on"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.test").state == "on"

    # test event for new unconfigured sensor
    event_callback({"id": "protocol2_0_1", "command": "on"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.protocol2_0_1").state == "on"

    # test changing state from HA propagates to RFLink
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.test"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test").state == "off"
    assert protocol.send_command_ack.call_args_list[0][0][0] == "protocol_0_0"
    assert protocol.send_command_ack.call_args_list[0][0][1] == "off"

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: f"{DOMAIN}.test"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test").state == "on"
    assert protocol.send_command_ack.call_args_list[1][0][1] == "on"

    # protocols supporting dimming and on/off should create hybrid light entity
    event_callback({"id": "newkaku_0_1", "command": "off"})
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: f"{DOMAIN}.newkaku_0_1"}
    )
    await hass.async_block_till_done()

    # dimmable should send highest dim level when turning on
    assert protocol.send_command_ack.call_args_list[2][0][1] == "15"

    # and send on command for fallback
    assert protocol.send_command_ack.call_args_list[3][0][1] == "on"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: f"{DOMAIN}.newkaku_0_1", ATTR_BRIGHTNESS: 128},
    )
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[4][0][1] == "7"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: f"{DOMAIN}.dim_test", ATTR_BRIGHTNESS: 128},
    )
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[5][0][1] == "7"


async def test_firing_bus_event(hass: HomeAssistant, monkeypatch) -> None:
    """Incoming RFLink command events should be put on the HA event bus."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {
                    "name": "test",
                    "aliases": ["test_alias_0_0"],
                    "fire_event": True,
                }
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    calls = []

    @callback
    def listener(event):
        calls.append(event)

    hass.bus.async_listen_once(EVENT_BUTTON_PRESSED, listener)

    # test event for new unconfigured sensor
    event_callback({"id": "protocol_0_0", "command": "off"})
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert calls[0].data == {"state": "off", "entity_id": f"{DOMAIN}.test"}


async def test_signal_repetitions(hass: HomeAssistant, monkeypatch) -> None:
    """Command should be sent amount of configured repetitions."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "device_defaults": {"signal_repetitions": 3},
            "devices": {
                "protocol_0_0": {"name": "test", "signal_repetitions": 2},
                "protocol_0_1": {"name": "test1"},
                "newkaku_0_1": {"type": "hybrid"},
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, protocol, _ = await mock_rflink(
        hass, config, DOMAIN, monkeypatch
    )

    # test if signal repetition is performed according to configuration
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.test"}
    )

    # wait for commands and repetitions to finish
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 2

    # test if default apply to configured devices
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.test1"}
    )

    # wait for commands and repetitions to finish
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 5

    # test if device defaults apply to newly created devices
    event_callback({"id": "protocol_0_2", "command": "off"})

    # make sure entity is created before setting state
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.protocol_0_2"}
    )

    # wait for commands and repetitions to finish
    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_count == 8


async def test_signal_repetitions_alternation(hass: HomeAssistant, monkeypatch) -> None:
    """Simultaneously switching entities must alternate repetitions."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {"name": "test", "signal_repetitions": 2},
                "protocol_0_1": {"name": "test1", "signal_repetitions": 2},
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.test"}
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.test1"}
    )

    await hass.async_block_till_done()

    assert protocol.send_command_ack.call_args_list[0][0][0] == "protocol_0_0"
    assert protocol.send_command_ack.call_args_list[1][0][0] == "protocol_0_1"
    assert protocol.send_command_ack.call_args_list[2][0][0] == "protocol_0_0"
    assert protocol.send_command_ack.call_args_list[3][0][0] == "protocol_0_1"


async def test_signal_repetitions_cancelling(hass: HomeAssistant, monkeypatch) -> None:
    """Cancel outstanding repetitions when state changed."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {"protocol_0_0": {"name": "test", "signal_repetitions": 3}},
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.test"}
    )

    # Get background service time to start running
    await asyncio.sleep(0)
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: f"{DOMAIN}.test"}, blocking=True
    )
    await hass.async_block_till_done()

    assert [call[0][1] for call in protocol.send_command_ack.call_args_list] == [
        "off",
        "on",
        "on",
        "on",
    ]


async def test_type_toggle(hass: HomeAssistant, monkeypatch) -> None:
    """Test toggle type lights (on/on)."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {"toggle_0_0": {"name": "toggle_test", "type": "toggle"}},
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # default value = 'off'
    assert hass.states.get(f"{DOMAIN}.toggle_test").state == "off"

    # test sending 'on' command, must set state = 'on'
    event_callback({"id": "toggle_0_0", "command": "on"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.toggle_test").state == "on"

    # test sending 'on' command again, must set state = 'off'
    event_callback({"id": "toggle_0_0", "command": "on"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.toggle_test").state == "off"

    # test async_turn_off, must set state = 'on' ('off' + toggle)
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: f"{DOMAIN}.toggle_test"}
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.toggle_test").state == "on"

    # test async_turn_on, must set state = 'off' (yes, sounds crazy)
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: f"{DOMAIN}.toggle_test"}
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.toggle_test").state == "off"


async def test_set_level_command(hass: HomeAssistant, monkeypatch) -> None:
    """Test 'set_level=XX' events."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "newkaku_12345678_0": {"name": "l1"},
                "test_no_dimmable": {"name": "l2"},
                "test_dimmable": {"name": "l3", "type": "dimmable"},
                "test_hybrid": {"name": "l4", "type": "hybrid"},
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test sending command to a newkaku device
    event_callback({"id": "newkaku_12345678_0", "command": "set_level=10"})
    await hass.async_block_till_done()
    # should affect state
    state = hass.states.get(f"{DOMAIN}.l1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 170
    # turn off
    event_callback({"id": "newkaku_12345678_0", "command": "off"})
    await hass.async_block_till_done()
    state = hass.states.get(f"{DOMAIN}.l1")
    assert state
    assert state.state == STATE_OFF
    # off light shouldn't have brightness
    assert not state.attributes.get(ATTR_BRIGHTNESS)
    # turn on
    event_callback({"id": "newkaku_12345678_0", "command": "on"})
    await hass.async_block_till_done()
    state = hass.states.get(f"{DOMAIN}.l1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 170

    # test sending command to a no dimmable device
    event_callback({"id": "test_no_dimmable", "command": "set_level=10"})
    await hass.async_block_till_done()
    # should NOT affect state
    state = hass.states.get(f"{DOMAIN}.l2")
    assert state
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_BRIGHTNESS)

    # test sending command to a dimmable device
    event_callback({"id": "test_dimmable", "command": "set_level=5"})
    await hass.async_block_till_done()
    # should affect state
    state = hass.states.get(f"{DOMAIN}.l3")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 85

    # test sending command to a hybrid device
    event_callback({"id": "test_hybrid", "command": "set_level=15"})
    await hass.async_block_till_done()
    # should affect state
    state = hass.states.get(f"{DOMAIN}.l4")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    event_callback({"id": "test_hybrid", "command": "off"})
    await hass.async_block_till_done()
    # should affect state
    state = hass.states.get(f"{DOMAIN}.l4")
    assert state
    assert state.state == STATE_OFF
    # off light shouldn't have brightness
    assert not state.attributes.get(ATTR_BRIGHTNESS)

    event_callback({"id": "test_hybrid", "command": "set_level=0"})
    await hass.async_block_till_done()
    # should affect state
    state = hass.states.get(f"{DOMAIN}.l4")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 0


async def test_group_alias(hass: HomeAssistant, monkeypatch) -> None:
    """Group aliases should only respond to group commands (allon/alloff)."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {"name": "test", "group_aliases": ["test_group_0_0"]},
                "protocol_0_1": {
                    "name": "test2",
                    "type": "dimmable",
                    "group_aliases": ["test_group_0_0"],
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # test sending group command to group alias
    event_callback({"id": "test_group_0_0", "command": "allon"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.test").state == "on"
    assert hass.states.get(f"{DOMAIN}.test2").state == "on"

    # test sending group command to group alias
    event_callback({"id": "test_group_0_0", "command": "off"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.test").state == "on"
    assert hass.states.get(f"{DOMAIN}.test2").state == "on"


async def test_nogroup_alias(hass: HomeAssistant, monkeypatch) -> None:
    """Non group aliases should not respond to group commands."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {
                    "name": "test",
                    "nogroup_aliases": ["test_nogroup_0_0"],
                }
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # test sending group command to nogroup alias
    event_callback({"id": "test_nogroup_0_0", "command": "allon"})
    await hass.async_block_till_done()
    # should not affect state
    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # test sending group commands to nogroup alias
    event_callback({"id": "test_nogroup_0_0", "command": "on"})
    await hass.async_block_till_done()
    # should affect state
    assert hass.states.get(f"{DOMAIN}.test").state == "on"


async def test_nogroup_device_id(hass: HomeAssistant, monkeypatch) -> None:
    """Device id that do not respond to group commands (allon/alloff)."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {"test_nogroup_0_0": {"name": "test", "group": False}},
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # test sending group command to nogroup
    event_callback({"id": "test_nogroup_0_0", "command": "allon"})
    await hass.async_block_till_done()
    # should not affect state
    assert hass.states.get(f"{DOMAIN}.test").state == "off"

    # test sending group command to nogroup
    event_callback({"id": "test_nogroup_0_0", "command": "on"})
    await hass.async_block_till_done()
    # should affect state
    assert hass.states.get(f"{DOMAIN}.test").state == "on"


async def test_disable_automatic_add(hass: HomeAssistant, monkeypatch) -> None:
    """If disabled new devices should not be automatically added."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {"platform": "rflink", "automatic_add": False},
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({"id": "protocol_0_0", "command": "off"})
    await hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get(f"{DOMAIN}.protocol_0_0")


async def test_restore_state(hass: HomeAssistant, monkeypatch) -> None:
    """Ensure states are restored on startup."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "NewKaku_12345678_0": {"name": "l1", "type": "hybrid"},
                "test_restore_2": {"name": "l2"},
                "test_restore_3": {"name": "l3"},
                "test_restore_4": {"name": "l4", "type": "dimmable"},
                "test_restore_5": {"name": "l5", "type": "dimmable"},
            },
        },
    }

    mock_restore_cache(
        hass,
        (
            State(f"{DOMAIN}.l1", STATE_ON, {ATTR_BRIGHTNESS: "123"}),
            State(f"{DOMAIN}.l2", STATE_ON, {ATTR_BRIGHTNESS: "321"}),
            State(f"{DOMAIN}.l3", STATE_OFF),
            State(f"{DOMAIN}.l5", STATE_ON, {ATTR_BRIGHTNESS: "222"}),
        ),
    )

    hass.set_state(CoreState.starting)

    # setup mocking rflink module
    _, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # hybrid light must restore brightness
    state = hass.states.get(f"{DOMAIN}.l1")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 123

    # normal light do NOT must restore brightness
    state = hass.states.get(f"{DOMAIN}.l2")
    assert state
    assert state.state == STATE_ON
    assert not state.attributes.get(ATTR_BRIGHTNESS)

    # OFF state also restores (or not)
    state = hass.states.get(f"{DOMAIN}.l3")
    assert state
    assert state.state == STATE_OFF

    # not cached light must default values
    state = hass.states.get(f"{DOMAIN}.l4")
    assert state
    assert state.state == STATE_OFF
    # off light shouldn't have brightness
    assert not state.attributes.get(ATTR_BRIGHTNESS)
    assert state.attributes["assumed_state"]

    # test coverage for dimmable light
    state = hass.states.get(f"{DOMAIN}.l5")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 222
