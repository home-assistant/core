"""The tests for the Command line switch platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components.command_line import DOMAIN
from homeassistant.components.command_line.switch import CommandSwitch
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_state_integration_yaml(hass: HomeAssistant) -> None:
    """Test with none state."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_on": f"echo 1 > {path}",
                            "command_off": f"echo 0 > {path}",
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF


async def test_state_value(hass: HomeAssistant) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_state": f"cat {path}",
                            "command_on": f"echo 1 > {path}",
                            "command_off": f"echo 0 > {path}",
                            "value_template": '{{ value=="1" }}',
                            "icon": (
                                '{% if value=="1" %} mdi:on {% else %} mdi:off {% endif %}'
                            ),
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON
        assert entity_state.attributes.get("icon") == "mdi:on"

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF
        assert entity_state.attributes.get("icon") == "mdi:off"


async def test_state_json_value(hass: HomeAssistant) -> None:
    """Test with state JSON value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        oncmd = json.dumps({"status": "ok"})
        offcmd = json.dumps({"status": "nope"})

        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_state": f"cat {path}",
                            "command_on": f"echo '{oncmd}' > {path}",
                            "command_off": f"echo '{offcmd}' > {path}",
                            "value_template": '{{ value_json.status=="ok" }}',
                            "icon": (
                                '{% if value_json.status=="ok" %} mdi:on'
                                "{% else %} mdi:off {% endif %}"
                            ),
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON
        assert entity_state.attributes.get("icon") == "mdi:on"

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF
        assert entity_state.attributes.get("icon") == "mdi:off"


async def test_state_code(hass: HomeAssistant) -> None:
    """Test with state code."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_state": f"cat {path}",
                            "command_on": f"echo 1 > {path}",
                            "command_off": f"echo 0 > {path}",
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        assert entity_state
        assert entity_state.state == STATE_ON


async def test_assumed_state_should_be_true_if_command_state_is_none(
    hass: HomeAssistant,
) -> None:
    """Test with state value."""

    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "switch": {
                        "command_on": "echo 'on command'",
                        "command_off": "echo 'off command'",
                        "name": "Test",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.attributes["assumed_state"]


async def test_assumed_state_should_absent_if_command_state_present(
    hass: HomeAssistant,
) -> None:
    """Test with state value."""

    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "switch": {
                        "command_on": "echo 'on command'",
                        "command_off": "echo 'off command'",
                        "command_state": "cat {}",
                        "name": "Test",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert "assumed_state" not in entity_state.attributes


async def test_name_is_set_correctly(hass: HomeAssistant) -> None:
    """Test that name is set correctly."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "switch": {
                        "command_on": "echo 'on command'",
                        "command_off": "echo 'off command'",
                        "name": "Test friendly name!",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test_friendly_name")
    assert entity_state
    assert entity_state.name == "Test friendly name!"


async def test_switch_command_state_fail(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that switch failures are handled correctly."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "switch": {
                        "command_on": "exit 0",
                        "command_off": "exit 0'",
                        "command_state": "echo 1",
                        "name": "Test",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("switch.test")
    assert entity_state
    assert entity_state.state == "on"

    assert "Command failed" in caplog.text


async def test_switch_command_state_code_exceptions(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that switch state code exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_on": "exit 0",
                            "command_off": "exit 0'",
                            "command_state": "echo 1",
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert check_output.called
        assert "Timeout for command" in caplog.text

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert check_output.called
        assert "Error trying to exec command" in caplog.text


async def test_switch_command_state_value_exceptions(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that switch state value exceptions are handled correctly."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        side_effect=[
            subprocess.TimeoutExpired("cmd", 10),
            subprocess.SubprocessError(),
        ],
    ) as check_output:
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_on": "exit 0",
                            "command_off": "exit 0'",
                            "command_state": "echo 1",
                            "value_template": '{{ value=="1" }}',
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert check_output.call_count == 1
        assert "Timeout for command" in caplog.text

        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        assert check_output.call_count == 2
        assert "Error trying to exec command" in caplog.text


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id option and if it only creates one switch per id."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "switch": {
                        "command_on": "echo on",
                        "command_off": "echo off",
                        "unique_id": "unique",
                        "name": "Test",
                    }
                },
                {
                    "switch": {
                        "command_on": "echo on",
                        "command_off": "echo off",
                        "unique_id": "not-so-unique-anymore",
                        "name": "Test2",
                    }
                },
                {
                    "switch": {
                        "command_on": "echo on",
                        "command_off": "echo off",
                        "unique_id": "not-so-unique-anymore",
                        "name": "Test3",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id("switch", "command_line", "unique")
    assert entity_registry.async_get_entity_id(
        "switch", "command_line", "not-so-unique-anymore"
    )


async def test_command_failure(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test command failure."""

    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "switch": {
                        "command_off": "exit 33",
                        "name": "Test",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.test"}, blocking=True
    )
    assert "return code 33" in caplog.text


async def test_templating(hass: HomeAssistant) -> None:
    """Test with templating."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "switch_status")
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_state": f"cat {path}",
                            "command_on": f"echo 1 > {path}",
                            "command_off": f"echo 0 > {path}",
                            "value_template": '{{ value=="1" }}',
                            "icon": (
                                '{% if this.state=="on" %} mdi:on {% else %} mdi:off {% endif %}'
                            ),
                            "name": "Test",
                        }
                    },
                    {
                        "switch": {
                            "command_state": f"cat {path}",
                            "command_on": f"echo 1 > {path}",
                            "command_off": f"echo 0 > {path}",
                            "value_template": '{{ value=="1" }}',
                            "icon": (
                                '{% if states("switch.test2")=="on" %} mdi:on {% else %} mdi:off {% endif %}'
                            ),
                            "name": "Test2",
                        },
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("switch.test")
        entity_state2 = hass.states.get("switch.test2")
        assert entity_state.state == STATE_OFF
        assert entity_state2.state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test"},
            blocking=True,
        )
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test2"},
            blocking=True,
        )

        entity_state = hass.states.get("switch.test")
        entity_state2 = hass.states.get("switch.test2")
        assert entity_state.state == STATE_ON
        assert entity_state.attributes.get("icon") == "mdi:on"
        assert entity_state2.state == STATE_ON
        assert entity_state2.attributes.get("icon") == "mdi:on"


async def test_updating_to_often(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling updating when command already running."""

    called = []
    wait_till_event = asyncio.Event()
    wait_till_event.set()

    class MockCommandSwitch(CommandSwitch):
        """Mock entity that updates."""

        async def _async_update(self) -> None:
            """Update entity."""
            called.append(1)
            # Wait till event is set
            await wait_till_event.wait()

    with patch(
        "homeassistant.components.command_line.switch.CommandSwitch",
        side_effect=MockCommandSwitch,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_state": "echo 1",
                            "command_on": "echo 2",
                            "command_off": "echo 3",
                            "name": "Test",
                            "scan_interval": 10,
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    assert not called
    assert (
        "Updating Command Line Switch Test took longer than the scheduled update interval"
        not in caplog.text
    )
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=11))
    await hass.async_block_till_done()
    assert called
    called.clear()

    assert (
        "Updating Command Line Switch Test took longer than the scheduled update interval"
        not in caplog.text
    )

    # Simulate update takes too long
    wait_till_event.clear()
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=10))
    await asyncio.sleep(0)
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=10))
    wait_till_event.set()

    # Finish processing update
    await hass.async_block_till_done()
    assert called
    assert (
        "Updating Command Line Switch Test took longer than the scheduled update interval"
        in caplog.text
    )


async def test_updating_manually(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling manual updating using homeassistant udate_entity service."""
    await setup.async_setup_component(hass, HA_DOMAIN, {})
    called = []

    class MockCommandSwitch(CommandSwitch):
        """Mock entity that updates."""

        async def _async_update(self) -> None:
            """Update slow."""
            called.append(1)

    with patch(
        "homeassistant.components.command_line.switch.CommandSwitch",
        side_effect=MockCommandSwitch,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "switch": {
                            "command_state": "echo 1",
                            "command_on": "echo 2",
                            "command_off": "echo 3",
                            "name": "Test",
                            "scan_interval": 10,
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert called
    called.clear()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["switch.test"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert called
