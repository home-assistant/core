"""The tests the cover command line platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import os
import tempfile
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components.command_line import DOMAIN
from homeassistant.components.command_line.cover import CommandCover
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, SCAN_INTERVAL
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.issue_registry as ir
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_no_covers_platform_yaml(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"50\n",
    ):
        assert await setup.async_setup_component(
            hass,
            COVER_DOMAIN,
            {
                COVER_DOMAIN: [
                    {"platform": "command_line", "covers": {}},
                ]
            },
        )
        await hass.async_block_till_done()
        assert "No covers added" in caplog.text

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_cover")
    assert issue.translation_key == "deprecated_platform_yaml"


async def test_state_value_platform_yaml(hass: HomeAssistant) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "cover_status")
        assert await setup.async_setup_component(
            hass,
            COVER_DOMAIN,
            {
                COVER_DOMAIN: [
                    {
                        "platform": "command_line",
                        "covers": {
                            "test": {
                                "command_state": f"cat {path}",
                                "command_open": f"echo 1 > {path}",
                                "command_close": f"echo 1 > {path}",
                                "command_stop": f"echo 0 > {path}",
                                "value_template": "{{ value }}",
                                "friendly_name": "Test",
                            },
                        },
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "unknown"

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.test"},
            blocking=True,
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"


async def test_no_poll_when_cover_has_no_command_state(hass: HomeAssistant) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        assert await setup.async_setup_component(
            hass,
            COVER_DOMAIN,
            {
                COVER_DOMAIN: [
                    {"platform": "command_line", "covers": {"test": {}}},
                ]
            },
        )
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert not check_output.called


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "cover": {
                        "command_state": "echo state",
                        "name": "Test",
                    },
                }
            ]
        }
    ],
)
async def test_poll_when_cover_has_command_state(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test that the cover polls when there's a state  command."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        check_output.assert_called_once_with(
            "echo state",
            shell=True,  # noqa: S604 # shell by design
            timeout=15,
            close_fds=False,
        )


async def test_state_value(hass: HomeAssistant) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "cover_status")
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "cover": {
                            "command_state": f"cat {path}",
                            "command_open": f"echo 1 > {path}",
                            "command_close": f"echo 1 > {path}",
                            "command_stop": f"echo 0 > {path}",
                            "value_template": "{{ value }}",
                            "name": "Test",
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "unknown"

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.test"},
            blocking=True,
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.test"},
            blocking=True,
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: "cover.test"},
            blocking=True,
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "closed"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "cover": {
                        "command_open": "exit 1",
                        "name": "Test",
                    }
                }
            ]
        }
    ],
)
async def test_move_cover_failure(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test command failure."""

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )
    assert "Command failed" in caplog.text
    assert "return code 1" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "cover": {
                        "command_open": "echo open",
                        "command_close": "echo close",
                        "command_stop": "echo stop",
                        "unique_id": "unique",
                        "name": "Test",
                    }
                },
                {
                    "cover": {
                        "command_open": "echo open",
                        "command_close": "echo close",
                        "command_stop": "echo stop",
                        "unique_id": "not-so-unique-anymore",
                        "name": "Test2",
                    }
                },
                {
                    "cover": {
                        "command_open": "echo open",
                        "command_close": "echo close",
                        "command_stop": "echo stop",
                        "unique_id": "not-so-unique-anymore",
                        "name": "Test3",
                    }
                },
            ]
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, load_yaml_integration: None
) -> None:
    """Test unique_id option and if it only creates one cover per id."""
    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id("cover", "command_line", "unique")
    assert entity_registry.async_get_entity_id(
        "cover", "command_line", "not-so-unique-anymore"
    )


async def test_updating_to_often(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling updating when command already running."""

    called = []
    wait_till_event = asyncio.Event()
    wait_till_event.set()

    class MockCommandCover(CommandCover):
        """Mock entity that updates."""

        async def _async_update(self) -> None:
            """Update the entity."""
            called.append(1)
            # Add waiting time
            await wait_till_event.wait()

    with patch(
        "homeassistant.components.command_line.cover.CommandCover",
        side_effect=MockCommandCover,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "cover": {
                            "command_state": "echo 1",
                            "value_template": "{{ value }}",
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
        "Updating Command Line Cover Test took longer than the scheduled update interval"
        not in caplog.text
    )
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=11))
    await hass.async_block_till_done()
    assert called
    called.clear()

    assert (
        "Updating Command Line Cover Test took longer than the scheduled update interval"
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
        "Updating Command Line Cover Test took longer than the scheduled update interval"
        in caplog.text
    )


async def test_updating_manually(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling manual updating using homeassistant udate_entity service."""
    await setup.async_setup_component(hass, HA_DOMAIN, {})
    called = []

    class MockCommandCover(CommandCover):
        """Mock entity that updates."""

        async def _async_update(self) -> None:
            """Update."""
            called.append(1)

    with patch(
        "homeassistant.components.command_line.cover.CommandCover",
        side_effect=MockCommandCover,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "cover": {
                            "command_state": "echo 1",
                            "value_template": "{{ value }}",
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
        {ATTR_ENTITY_ID: ["cover.test"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert called
