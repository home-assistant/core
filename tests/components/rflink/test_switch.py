"""Test for RFlink switch components.

Test setup of rflink switch component/platform. State tracking and
control of Rflink switch devices.

"""

import pytest

from homeassistant.components.rflink.entity import EVENT_BUTTON_PRESSED
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

DOMAIN = "switch"

CONFIG = {
    "rflink": {
        "port": "/dev/ttyABC0",
        "ignore_devices": ["ignore_wildcard_*", "ignore_sensor"],
    },
    DOMAIN: {
        "platform": "rflink",
        "devices": {"protocol_0_0": {"name": "test", "aliases": ["test_alias_0_0"]}},
    },
}


async def test_default_setup(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test all basic functionality of the rflink switch component."""
    # setup mocking rflink module
    event_callback, create, protocol, _ = await mock_rflink(
        hass, CONFIG, DOMAIN, monkeypatch
    )

    # make sure arguments are passed
    assert create.call_args_list[0][1]["ignore"]

    # test default state of switch loaded from config
    switch_initial = hass.states.get("switch.test")
    assert switch_initial.state == "off"
    assert switch_initial.attributes["assumed_state"]

    # switch should follow state of the hardware device by interpreting
    # incoming events for its name and aliases

    # mock incoming command event for this device
    event_callback({"id": "protocol_0_0", "command": "on"})
    await hass.async_block_till_done()

    switch_after_first_command = hass.states.get("switch.test")
    assert switch_after_first_command.state == "on"
    # also after receiving first command state not longer has to be assumed
    assert not switch_after_first_command.attributes.get("assumed_state")

    # mock incoming command event for this device
    event_callback({"id": "protocol_0_0", "command": "off"})
    await hass.async_block_till_done()

    assert hass.states.get("switch.test").state == "off"

    # test following aliases
    # mock incoming command event for this device alias
    event_callback({"id": "test_alias_0_0", "command": "on"})
    await hass.async_block_till_done()

    assert hass.states.get("switch.test").state == "on"

    # The switch component does not support adding new devices for incoming
    # events because every new unknown device is added as a light by default.

    # test changing state from HA propagates to Rflink
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


async def test_group_alias(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Group aliases should only respond to group commands (allon/alloff)."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {"name": "test", "group_aliases": ["test_group_0_0"]}
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

    # test sending group command to group alias
    event_callback({"id": "test_group_0_0", "command": "off"})
    await hass.async_block_till_done()

    assert hass.states.get(f"{DOMAIN}.test").state == "on"


async def test_nogroup_alias(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    # test sending group command to nogroup alias
    event_callback({"id": "test_nogroup_0_0", "command": "on"})
    await hass.async_block_till_done()
    # should affect state
    assert hass.states.get(f"{DOMAIN}.test").state == "on"


async def test_nogroup_device_id(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
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


async def test_device_defaults(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Event should fire if device_defaults config says so."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "device_defaults": {"fire_event": True},
            "devices": {
                "protocol_0_0": {"name": "test", "aliases": ["test_alias_0_0"]}
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


async def test_not_firing_default(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """By default no bus events should be fired."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {"name": "test", "aliases": ["test_alias_0_0"]}
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

    assert not calls, "an event has been fired"


async def test_restore_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure states are restored on startup."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "test": {"name": "s1", "aliases": ["test_alias_0_0"]},
                "switch_test": {"name": "s2"},
                "switch_s3": {"name": "s3"},
            },
        },
    }

    mock_restore_cache(
        hass, (State(f"{DOMAIN}.s1", STATE_ON), State(f"{DOMAIN}.s2", STATE_OFF))
    )

    hass.set_state(CoreState.starting)

    # setup mocking rflink module
    _, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    state = hass.states.get(f"{DOMAIN}.s1")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get(f"{DOMAIN}.s2")
    assert state
    assert state.state == STATE_OFF

    # not cached switch must default values
    state = hass.states.get(f"{DOMAIN}.s3")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes["assumed_state"]
