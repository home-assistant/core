"""The tests for the Command line switch platform."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.command_line import DOMAIN
from homeassistant.components.switch import DOMAIN as PLATFORM_DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

ENTITY_NAME = {"name": "Test"}
tmpdir = tempfile.TemporaryDirectory()
PATH = os.path.join(tmpdir.name, "switch_status")
ONCMD = json.dumps({"status": "ok"})
OFFCMD = json.dumps({"status": "nope"})


@pytest.fixture(scope="session", autouse=True)
def clean_tmpdir():
    """Cleanup tmpdir at the end of session."""
    yield
    tmpdir.cleanup()


@pytest.fixture(autouse=True)
def clean_tmpfile():
    """Clear tmpfile after each test."""
    yield
    with open(PATH, "w"):
        pass


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": f"echo 1 > {PATH}",
                    "command_off": f"echo 0 > {PATH}",
                },
            },
        },
    ],
)
async def test_state_none(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test with none state."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_ON

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_state": f"cat {PATH}",
                    "command_on": f"echo 1 > {PATH}",
                    "command_off": f"echo 0 > {PATH}",
                    "value_template": '{{ value=="1" }}',
                    "icon_template": '{% if value=="1" %} mdi:on {% else %} mdi:off {% endif %}',
                },
            },
        },
    ],
)
async def test_state_value(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test with state value."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.attributes.get("icon") == "mdi:on"

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF
    assert entity_state.attributes.get("icon") == "mdi:off"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_state": f"cat {PATH}",
                    "command_on": f"echo '{ONCMD}' > {PATH}",
                    "command_off": f"echo '{OFFCMD}' > {PATH}",
                    "value_template": '{{ value_json.status=="ok" }}',
                    "icon_template": '{% if value_json.status=="ok" %} mdi:on {% else %} mdi:off {% endif %}',
                },
            },
        },
    ],
)
async def test_state_json_value(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test with state JSON value."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.attributes.get("icon") == "mdi:on"

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF
    assert entity_state.attributes.get("icon") == "mdi:off"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_state": f"cat {PATH}",
                    "command_on": f"echo 1 > {PATH}",
                    "command_off": f"echo 0 > {PATH}",
                },
            },
        },
    ],
)
async def test_state_code(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test with state code."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_OFF

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_ON

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == STATE_ON


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": "echo 'on command'",
                    "command_off": "echo 'off command'",
                },
            },
        },
    ],
)
async def test_assumed_state_should_be_true_if_command_state_is_none(
    hass: HomeAssistant,
    start_ha: Callable,
) -> None:
    """Test with state value."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.attributes["assumed_state"]


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": "echo 'on command'",
                    "command_off": "echo 'off command'",
                    "command_state": "cat {}",
                },
            },
        },
    ],
)
async def test_assumed_state_should_absent_if_command_state_present(
    hass: HomeAssistant,
    start_ha: Callable,
) -> None:
    """Test with state value."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert "assumed_state" not in entity_state.attributes


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": "echo 'on command'",
                    "command_off": "echo 'off command'",
                    "friendly_name": "Test friendly name!",
                },
            },
        },
    ],
)
async def test_name_is_set_correctly(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test that name is set correctly."""
    await start_ha()

    entity_state = hass.states.get("switch.test")
    assert entity_state.name == "Test friendly name!"


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": "exit 0",
                    "command_off": "exit 0'",
                    "command_state": "echo 1",
                },
            },
        },
    ],
)
async def test_switch_command_state_fail(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test that switch failures are handled correctly."""
    await start_ha()

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state.state == "on"

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state.state == "on"

    assert "Command failed" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": "exit 0",
                    "command_off": "exit 0'",
                    "command_state": "echo 1",
                },
            },
        },
    ],
)
async def test_switch_command_state_code_exceptions(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test that switch state code exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await start_ha()
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert check_output.called
        assert "Timeout for command" in caplog.text

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert check_output.called
        assert "Error trying to exec command" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: {
                    **ENTITY_NAME,
                    "command_on": "exit 0",
                    "command_off": "exit 0'",
                    "command_state": "echo 1",
                    "value_template": '{{ value=="1" }}',
                },
            },
        },
    ],
)
async def test_switch_command_state_value_exceptions(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test that switch state value exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await start_ha()
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert check_output.call_count == 1
        assert "Timeout for command" in caplog.text

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert check_output.call_count == 2
        assert "Error trying to exec command" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: [],
            },
        },
    ],
)
async def test_no_switches(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test with no switches."""
    await start_ha()

    assert "No switches" in caplog.text


@pytest.mark.parametrize("domains", [[(DOMAIN, 1)]])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                PLATFORM_DOMAIN: [
                    {
                        "command_on": "echo on",
                        "command_off": "echo off",
                        "unique_id": "unique",
                    },
                    {
                        "command_on": "echo on",
                        "command_off": "echo off",
                        "unique_id": "not-so-unique-anymore",
                    },
                    {
                        "command_on": "echo on",
                        "command_off": "echo off",
                        "unique_id": "not-so-unique-anymore",
                    },
                ],
            },
        },
    ],
)
async def test_unique_id(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test unique_id option and if it only creates one switch per id."""
    await start_ha()

    assert len(hass.states.async_all()) == 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "unique") is not None
    assert (
        ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "not-so-unique-anymore")
        is not None
    )
