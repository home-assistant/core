"""The tests for the Command line switch platform."""
import json
import os
import tempfile

from homeassistant import setup
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.typing import Any, Dict, HomeAssistantType


async def setup_test_entity(
    hass: HomeAssistantType, config_dict: Dict[str, Any]
) -> None:
    """Set up a test command line switch entity."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"platform": "command_line", "switches": {"test": config_dict}},
            ]
        },
    )
    await hass.async_block_till_done()


async def test_state_none(hass: HomeAssistantType) -> None:
    """Test with none state."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup_test_entity(
            hass,
            {
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
            },
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF


async def test_state_value(hass: HomeAssistantType) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup_test_entity(
            hass,
            {
                "command_state": f"cat {path}",
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
                "value_template": '{{ value=="1" }}',
            },
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF


async def test_state_json_value(hass: HomeAssistantType) -> None:
    """Test with state JSON value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        oncmd = json.dumps({"status": "ok"})
        offcmd = json.dumps({"status": "nope"})

        await setup_test_entity(
            hass,
            {
                "command_state": f"cat {path}",
                "command_on": f"echo '{oncmd}' > {path}",
                "command_off": f"echo '{offcmd}' > {path}",
                "value_template": '{{ value_json.status=="ok" }}',
            },
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF


async def test_state_code(hass: HomeAssistantType) -> None:
    """Test with state code."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup_test_entity(
            hass,
            {
                "command_state": f"cat {path}",
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
            },
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON


async def test_assumed_state_should_be_true_if_command_state_is_none(
    hass: HomeAssistantType,
) -> None:
    """Test with state value."""

    await setup_test_entity(
        hass,
        {
            "command_on": "echo 'on command'",
            "command_off": "echo 'off command'",
        },
    )
    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.attributes["assumed_state"]


async def test_assumed_state_should_absent_if_command_state_present(
    hass: HomeAssistantType,
) -> None:
    """Test with state value."""

    await setup_test_entity(
        hass,
        {
            "command_on": "echo 'on command'",
            "command_off": "echo 'off command'",
            "command_state": "cat {}",
        },
    )
    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert "assumed_state" not in entity_state.attributes


async def test_name_is_set_correctly(hass: HomeAssistantType) -> None:
    """Test that name is set correctly."""
    await setup_test_entity(
        hass,
        {
            "command_on": "echo 'on command'",
            "command_off": "echo 'off command'",
            "friendly_name": "Test friendly name!",
        },
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state.name == "Test friendly name!"
