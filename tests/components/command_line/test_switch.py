"""The tests for the Command line switch platform."""
import json
import os
import tempfile

import homeassistant.components.command_line.switch as command_line
import homeassistant.components.switch as switch
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component


async def test_state_none(hass):
    """Test with none state."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        test_switch = {
            "command_on": f"echo 1 > {path}",
            "command_off": f"echo 0 > {path}",
        }
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "command_line",
                    "switches": {"test": test_switch},
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_ON == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state


async def test_state_value(hass):
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        test_switch = {
            "command_state": f"cat {path}",
            "command_on": f"echo 1 > {path}",
            "command_off": f"echo 0 > {path}",
            "value_template": '{{ value=="1" }}',
        }
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "command_line",
                    "switches": {"test": test_switch},
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_ON == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state


async def test_state_json_value(hass):
    """Test with state JSON value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        oncmd = json.dumps({"status": "ok"})
        offcmd = json.dumps({"status": "nope"})
        test_switch = {
            "command_state": f"cat {path}",
            "command_on": f"echo '{oncmd}' > {path}",
            "command_off": f"echo '{offcmd}' > {path}",
            "value_template": '{{ value_json.status=="ok" }}',
        }
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "command_line",
                    "switches": {"test": test_switch},
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_ON == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state


async def test_state_code(hass):
    """Test with state code."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        test_switch = {
            "command_state": f"cat {path}",
            "command_on": f"echo 1 > {path}",
            "command_off": f"echo 0 > {path}",
        }
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "command_line",
                    "switches": {"test": test_switch},
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.test")
        assert STATE_OFF == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_ON == state.state

        await hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        state = hass.states.get("switch.test")
        assert STATE_ON == state.state


def test_assumed_state_should_be_true_if_command_state_is_none(hass):
    """Test with state value."""
    # args: hass, device_name, friendly_name, command_on, command_off,
    #       command_state, value_template
    init_args = [
        hass,
        "test_device_name",
        "Test friendly name!",
        "echo 'on command'",
        "echo 'off command'",
        None,
        None,
        15,
    ]

    no_state_device = command_line.CommandSwitch(*init_args)
    assert no_state_device.assumed_state

    # Set state command
    init_args[-3] = "cat {}"

    state_device = command_line.CommandSwitch(*init_args)
    assert not state_device.assumed_state


def test_entity_id_set_correctly(hass):
    """Test that entity_id is set correctly from object_id."""
    init_args = [
        hass,
        "test_device_name",
        "Test friendly name!",
        "echo 'on command'",
        "echo 'off command'",
        False,
        None,
        15,
    ]

    test_switch = command_line.CommandSwitch(*init_args)
    assert test_switch.entity_id == "switch.test_device_name"
    assert test_switch.name == "Test friendly name!"
