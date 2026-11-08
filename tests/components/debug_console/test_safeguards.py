"""Tests for the safeguards of the Debug console."""

import logging
import re
from typing import Any

import pytest
from pytest_homeassistant.common import CLIENT_ID, MockUser
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components.debug_console.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_VERSION,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import CONSOLE_COMMANDS

SESSION_ID = "test-session"
EXECUTE = {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"}


@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the Debug console, without anyone having accepted the warning."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


def _logged_user(user: MockUser) -> str:
    """Return a pattern of how a user is logged, with their login and address."""
    return rf"{re.escape(user.name)} \(user {user.id}, refresh token \w+, from \S+\)"


def _stored_acceptances(accepted: dict[str, Any]) -> dict[str, Any]:
    """Return the storage of the console, with these acceptances."""
    return {
        "version": 1,
        "key": DOMAIN,
        "data": {CONF_WARNING_ACCEPTED: accepted},
    }


async def _async_send(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> dict[str, Any]:
    """Send a command and return the response message."""
    await websocket_client.send_json_auto_id(command)
    msg = await websocket_client.receive_json()
    assert msg["type"] == TYPE_RESULT
    return msg


async def test_warning_required_until_accepted(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    hass_storage: dict[str, Any],
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

    acceptance = hass_storage[DOMAIN]["data"][CONF_WARNING_ACCEPTED][hass_admin_user.id]
    assert acceptance["version"] == WARNING_VERSION


async def test_older_warning_needs_accepting_again(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    hass_storage: dict[str, Any],
) -> None:
    """Test an acceptance of an older version of the warning no longer counts."""
    hass_storage[DOMAIN] = _stored_acceptances(
        {
            hass_admin_user.id: {
                "version": WARNING_VERSION - 1,
                "accepted_at": "2026-01-01T00:00:00+00:00",
            }
        }
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    client = await hass_ws_client(hass)

    msg = await _async_send(client, {"type": "debug_console/info"})

    assert msg["result"] == {"warning_required": True}


async def test_acceptance_of_removed_users_forgotten(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_storage: dict[str, Any]
) -> None:
    """Test acceptances of removed users are forgotten, also while not loaded."""
    other_user = await hass.auth.async_create_user("Other admin")
    acceptance = {"version": WARNING_VERSION, "accepted_at": "2026-01-01"}
    hass_storage[DOMAIN] = _stored_acceptances(
        {
            hass_admin_user.id: acceptance,
            other_user.id: acceptance,
            "removed-while-not-loaded": acceptance,
        }
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    assert set(hass_storage[DOMAIN]["data"][CONF_WARNING_ACCEPTED]) == {
        hass_admin_user.id,
        other_user.id,
    }

    await hass.auth.async_remove_user(other_user)
    await hass.async_block_till_done()

    assert set(hass_storage[DOMAIN]["data"][CONF_WARNING_ACCEPTED]) == {
        hass_admin_user.id
    }

    # Removing a user who never accepted the warning changes nothing.
    never_accepted = await hass.auth.async_create_user("Never accepted")
    await hass.auth.async_remove_user(never_accepted)
    await hass.async_block_till_done()

    assert set(hass_storage[DOMAIN]["data"][CONF_WARNING_ACCEPTED]) == {
        hass_admin_user.id
    }


async def test_logging_executions(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the code that runs is logged, with who ran it."""
    with caplog.at_level(logging.WARNING):
        await _async_send(websocket_client, {"type": "debug_console/warning/accept"})
        msg = await _async_send(websocket_client, {**EXECUTE, "code": "answer = 42"})

    assert msg["success"]
    assert re.search(
        _logged_user(hass_admin_user) + r" ran code in the debug console:\nanswer = 42",
        caplog.text,
    )


async def test_logging_inspection(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test objects that are expanded are logged, with who did."""
    await _async_send(websocket_client, {"type": "debug_console/warning/accept"})
    msg = await _async_send(
        websocket_client,
        {**EXECUTE, "code": "class Thing:\n    pass\n\nThing()"},
    )

    with caplog.at_level(logging.WARNING):
        msg = await _async_send(
            websocket_client,
            {
                "type": "debug_console/inspect",
                "session_id": SESSION_ID,
                "object_id": msg["result"]["result"]["object_id"],
            },
        )

    assert msg["success"]
    assert re.search(
        _logged_user(hass_admin_user) + " expanded a Thing in the debug console",
        caplog.text,
    )


async def test_logging_class_with_odd_name(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a class named by a subclass of str is logged without running it."""
    await _async_send(websocket_client, {"type": "debug_console/warning/accept"})
    msg = await _async_send(
        websocket_client,
        {
            **EXECUTE,
            "code": (
                "class Name(str):\n"
                "    def __str__(self):\n"
                "        raise SystemExit\n\n"
                "    def __format__(self, spec):\n"
                "        raise SystemExit\n\n"
                "class Thing:\n"
                "    pass\n\n"
                "Thing.__qualname__ = Name('Thing')\n"
                "Thing()"
            ),
        },
    )

    with caplog.at_level(logging.WARNING):
        msg = await _async_send(
            websocket_client,
            {
                "type": "debug_console/inspect",
                "session_id": SESSION_ID,
                "object_id": msg["result"]["result"]["object_id"],
            },
        )

    assert msg["success"]
    assert re.search(
        _logged_user(hass_admin_user) + " expanded a Thing in the debug console",
        caplog.text,
    )


async def test_logging_property_evaluation(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test properties that are evaluated are logged, with who did."""
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
    assert re.search(
        _logged_user(hass_admin_user) + r" evaluated Thing\.state in the debug console",
        caplog.text,
    )


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
