"""The tests the cover command line platform."""
from __future__ import annotations

import os
import tempfile
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config, setup
from homeassistant.components.cover import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_RELOAD,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, get_fixture_path


async def setup_test_entity(hass: HomeAssistant, config_dict: dict[str, Any]) -> None:
    """Set up a test command line notify service."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"platform": "command_line", "covers": config_dict},
            ]
        },
    )
    await hass.async_block_till_done()


async def test_no_covers(caplog: pytest.LogCaptureFixture, hass: HomeAssistant) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"50\n",
    ):
        await setup_test_entity(hass, {})
        assert "No covers added" in caplog.text


async def test_no_poll_when_cover_has_no_command_state(hass: HomeAssistant) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        await setup_test_entity(hass, {"test": {}})
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert not check_output.called


async def test_poll_when_cover_has_command_state(hass: HomeAssistant) -> None:
    """Test that the cover polls when there's a state  command."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        await setup_test_entity(hass, {"test": {"command_state": "echo state"}})
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        check_output.assert_called_once_with(
            "echo state",
            shell=True,  # nosec # shell by design
            timeout=15,
            close_fds=False,
        )


async def test_state_value(hass: HomeAssistant) -> None:
    """Test with state value."""
    with tempfile.TemporaryDirectory() as tempdirname:
        path = os.path.join(tempdirname, "cover_status")
        await setup_test_entity(
            hass,
            {
                "test": {
                    "command_state": f"cat {path}",
                    "command_open": f"echo 1 > {path}",
                    "command_close": f"echo 1 > {path}",
                    "command_stop": f"echo 0 > {path}",
                    "value_template": "{{ value }}",
                }
            },
        )

        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "unknown"

        await hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"

        await hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "open"

        await hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
        )
        entity_state = hass.states.get("cover.test")
        assert entity_state
        assert entity_state.state == "closed"


async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload command_line covers."""

    await setup_test_entity(
        hass,
        {
            "test": {
                "command_state": "echo open",
                "value_template": "{{ value }}",
            }
        },
    )
    entity_state = hass.states.get("cover.test")
    assert entity_state
    assert entity_state.state == "unknown"

    yaml_path = get_fixture_path("configuration.yaml", "command_line")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "command_line",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert not hass.states.get("cover.test")
    assert hass.states.get("cover.from_yaml")


async def test_move_cover_failure(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test command failure."""

    await setup_test_entity(
        hass,
        {"test": {"command_open": "exit 1"}},
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: "cover.test"}, blocking=True
    )
    assert "Command failed" in caplog.text
    assert "return code 1" in caplog.text


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id option and if it only creates one cover per id."""
    await setup_test_entity(
        hass,
        {
            "unique": {
                "command_open": "echo open",
                "command_close": "echo close",
                "command_stop": "echo stop",
                "unique_id": "unique",
            },
            "not_unique_1": {
                "command_open": "echo open",
                "command_close": "echo close",
                "command_stop": "echo stop",
                "unique_id": "not-so-unique-anymore",
            },
            "not_unique_2": {
                "command_open": "echo open",
                "command_close": "echo close",
                "command_stop": "echo stop",
                "unique_id": "not-so-unique-anymore",
            },
        },
    )

    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id("cover", "command_line", "unique")
    assert entity_registry.async_get_entity_id(
        "cover", "command_line", "not-so-unique-anymore"
    )
