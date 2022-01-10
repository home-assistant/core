"""The tests the cover command line platform."""
from __future__ import annotations

import os
import tempfile
from typing import Any, Callable
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.command_line import DOMAIN
from homeassistant.components.cover import DOMAIN as PLATFORM_DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_RELOAD,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, get_fixture_path

ENTITY_NAME = {"name": "Test"}
ENTITY_ID = "cover.test"
tmpdir = tempfile.TemporaryDirectory()
PATH = os.path.join(tmpdir.name, "cover_status")


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


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {},
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: [],
                },
            },
        ),
    ],
)
async def test_no_covers(caplog: Any, hass: HomeAssistant, start_ha: Callable) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        return_value=b"50\n",
    ):
        await start_ha()
        assert "No covers added" in caplog.text


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {
                        "test": {},
                    },
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        **ENTITY_NAME,
                    },
                },
            },
        ),
    ],
)
async def test_no_poll_when_cover_has_no_command_state(
    hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test that the cover does not polls when there's no state command."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        await start_ha()
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        assert not check_output.called


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {
                        "test": {
                            "command_state": "echo state",
                        },
                    },
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        **ENTITY_NAME,
                        "command_state": "echo state",
                    },
                },
            },
        ),
    ],
)
async def test_poll_when_cover_has_command_state(
    hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test that the cover polls when there's a state  command."""

    with patch(
        "homeassistant.components.command_line.subprocess.check_output",
        return_value=b"50\n",
    ) as check_output:
        await start_ha()
        async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        check_output.assert_called_once_with(
            "echo state", shell=True, timeout=15  # nosec # shell by design
        )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {
                        "test": {
                            "command_state": f"cat {PATH}",
                            "command_open": f"echo 1 > {PATH}",
                            "command_close": f"echo 1 > {PATH}",
                            "command_stop": f"echo 0 > {PATH}",
                            "value_template": "{{ value }}",
                        },
                    },
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        **ENTITY_NAME,
                        "command_state": f"cat {PATH}",
                        "command_open": f"echo 1 > {PATH}",
                        "command_close": f"echo 1 > {PATH}",
                        "command_stop": f"echo 0 > {PATH}",
                        "value_template": "{{ value }}",
                    },
                },
            },
        ),
    ],
)
async def test_state_value(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test with state value."""
    await start_ha()

    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unknown"

    await hass.services.async_call(
        PLATFORM_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state
    assert entity_state.state == "open"

    await hass.services.async_call(
        PLATFORM_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state
    assert entity_state.state == "open"

    await hass.services.async_call(
        PLATFORM_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state
    assert entity_state.state == "closed"


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {
                        "test": {
                            "command_state": "echo open",
                            "value_template": "{{ value }}",
                        },
                    },
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        **ENTITY_NAME,
                        "command_state": "echo open",
                        "value_template": "{{ value }}",
                    },
                },
            },
        ),
    ],
)
async def test_reload(hass: HomeAssistant, start_ha: Callable) -> None:
    """Verify we can reload command_line covers."""
    await start_ha()

    entity_state = hass.states.get(ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unknown"

    yaml_path = get_fixture_path("configuration.yaml", DOMAIN)
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert not hass.states.get(ENTITY_ID)
    assert hass.states.get("cover.from_yaml")


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {
                        "test": {"command_open": "exit 1"},
                    },
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {**ENTITY_NAME, "command_open": "exit 1"},
                },
            },
        ),
    ],
)
async def test_move_cover_failure(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test with state value."""
    await start_ha()

    await hass.services.async_call(
        PLATFORM_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert "Command failed" in caplog.text


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: {
                    "platform": DOMAIN,
                    "covers": {
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
                },
            },
        ),
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: [
                        {
                            "command_open": "echo open",
                            "command_close": "echo close",
                            "command_stop": "echo stop",
                            "unique_id": "unique",
                        },
                        {
                            "command_open": "echo open",
                            "command_close": "echo close",
                            "command_stop": "echo stop",
                            "unique_id": "not-so-unique-anymore",
                        },
                        {
                            "command_open": "echo open",
                            "command_close": "echo close",
                            "command_stop": "echo stop",
                            "unique_id": "not-so-unique-anymore",
                        },
                    ],
                },
            },
        ),
    ],
)
async def test_unique_id(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test unique_id option and if it only creates one cover per id."""
    await start_ha()

    assert len(hass.states.async_all()) == 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2
    assert ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "unique") is not None
    assert (
        ent_reg.async_get_entity_id(PLATFORM_DOMAIN, DOMAIN, "not-so-unique-anymore")
        is not None
    )
