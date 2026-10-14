"""Tests for the safeguards of the Debug console on release versions."""

from collections.abc import Generator
import logging
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.debug_console.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_VERSION,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant

from . import CONSOLE_COMMANDS

from tests.common import CLIENT_ID, MockConfigEntry, MockUser
from tests.typing import MockHAClientWebSocket, WebSocketGenerator

SESSION_ID = "test-session"
EXECUTE = {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"}


@pytest.fixture
def release_version() -> Generator[None]:
    """Run as a beta or stable version, where the safeguards apply."""
    with patch(
        "homeassistant.components.debug_console.safeguards.IS_DEVELOPMENT_VERSION",
        False,
    ):
        yield


async def _async_send(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> dict[str, Any]:
    """Send a command and return the response message."""
    await websocket_client.send_json_auto_id(command)
    msg = await websocket_client.receive_json()
    assert msg["type"] == TYPE_RESULT
    return msg


@pytest.mark.usefixtures("release_version")
async def test_warning_required_until_accepted(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
) -> None:
    """Test the console refuses to run code until the user accepts the warning."""
    msg = await _async_send(websocket_client, {"type": "debug_console/info"})
    assert msg["result"] == {"warning_required": True}

    msg = await _async_send(websocket_client, EXECUTE)
    assert not msg["success"]
    assert msg["error"]["code"] == "warning_not_accepted"

    msg = await _async_send(websocket_client, {"type": "debug_console/warning/accept"})
    assert msg["success"]

    msg = await _async_send(websocket_client, {"type": "debug_console/info"})
    assert msg["result"] == {"warning_required": False}

    msg = await _async_send(websocket_client, EXECUTE)
    assert msg["success"]

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    acceptance = entry.data[CONF_WARNING_ACCEPTED][hass_admin_user.id]
    assert acceptance["version"] == WARNING_VERSION


async def test_no_warning_on_development_version(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test development versions do not ask for the warning."""
    msg = await _async_send(websocket_client, {"type": "debug_console/info"})
    assert msg["result"] == {"warning_required": False}

    msg = await _async_send(websocket_client, EXECUTE)
    assert msg["success"]


@pytest.mark.usefixtures("release_version")
async def test_older_warning_needs_accepting_again(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test an acceptance of an older version of the warning no longer counts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_WARNING_ACCEPTED: {
                hass_admin_user.id: {
                    "version": WARNING_VERSION - 1,
                    "accepted_at": "2026-01-01T00:00:00+00:00",
                }
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)

    msg = await _async_send(client, {"type": "debug_console/info"})

    assert msg["result"] == {"warning_required": True}


async def test_acceptance_of_removed_users_forgotten(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test acceptances of removed users are forgotten, also while not loaded."""
    other_user = await hass.auth.async_create_user("Other admin")
    acceptance = {"version": WARNING_VERSION, "accepted_at": "2026-01-01"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_WARNING_ACCEPTED: {
                hass_admin_user.id: acceptance,
                other_user.id: acceptance,
                "removed-while-unloaded": acceptance,
            }
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    assert set(entry.data[CONF_WARNING_ACCEPTED]) == {
        hass_admin_user.id,
        other_user.id,
    }

    await hass.auth.async_remove_user(other_user)
    await hass.async_block_till_done()

    assert set(entry.data[CONF_WARNING_ACCEPTED]) == {hass_admin_user.id}

    # Removing a user who never accepted the warning changes nothing.
    never_accepted = await hass.auth.async_create_user("Never accepted")
    await hass.auth.async_remove_user(never_accepted)
    await hass.async_block_till_done()

    assert set(entry.data[CONF_WARNING_ACCEPTED]) == {hass_admin_user.id}


@pytest.mark.parametrize(
    ("development_version", "logged"),
    [
        pytest.param(False, True, id="release"),
        pytest.param(True, False, id="development"),
    ],
)
async def test_logging_executions(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
    development_version: bool,
    logged: bool,
) -> None:
    """Test release versions log the code that runs, with who ran it."""
    with (
        patch(
            "homeassistant.components.debug_console.safeguards.IS_DEVELOPMENT_VERSION",
            development_version,
        ),
        caplog.at_level(logging.WARNING),
    ):
        await _async_send(websocket_client, {"type": "debug_console/warning/accept"})
        msg = await _async_send(websocket_client, {**EXECUTE, "code": "answer = 42"})

    assert msg["success"]
    assert (
        f"{hass_admin_user.name} ran code in the debug console:\nanswer = 42"
        in caplog.text
    ) is logged


@pytest.mark.usefixtures("release_version")
async def test_logging_property_evaluation(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test release versions log properties that are evaluated, with who did."""
    await _async_send(websocket_client, {"type": "debug_console/warning/accept"})
    msg = await _async_send(
        websocket_client,
        {
            **EXECUTE,
            "code": "class Thing:\n    @property\n    def state(self):\n        return 1\n\nThing()",
        },
    )

    with caplog.at_level(logging.WARNING):
        msg = await _async_send(
            websocket_client,
            {
                "type": "debug_console/get_attribute",
                "session_id": SESSION_ID,
                "object_id": msg["result"]["result"]["object_id"],
                "attribute": "state",
            },
        )

    assert msg["success"]
    assert f"{hass_admin_user.name} evaluated Thing.state in the debug console" in (
        caplog.text
    )


@pytest.mark.usefixtures("release_version")
@pytest.mark.parametrize("command", CONSOLE_COMMANDS)
async def test_warning_required_per_user(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    hass_ws_client: WebSocketGenerator,
    command: dict[str, Any],
) -> None:
    """Test every console command needs each user to accept the warning."""
    other_user = await hass.auth.async_create_user(
        "Other admin", group_ids=["system-admin"]
    )
    refresh_token = await hass.auth.async_create_refresh_token(other_user, CLIENT_ID)
    other_client = await hass_ws_client(
        hass, hass.auth.async_create_access_token(refresh_token)
    )
    await _async_send(other_client, {"type": "debug_console/warning/accept"})

    msg = await _async_send(websocket_client, command)

    assert not msg["success"]
    assert msg["error"]["code"] == "warning_not_accepted"
