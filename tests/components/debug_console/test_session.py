"""Tests for the sessions of the Debug console."""

import threading
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.debug_console.const import SESSION_TIMEOUT
from homeassistant.components.websocket_api import ERR_INVALID_FORMAT, ERR_NOT_FOUND
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import SESSION_ID, async_execute, async_send

from tests.common import CLIENT_ID, MockConfigEntry, async_fire_time_changed
from tests.typing import MockHAClientWebSocket, WebSocketGenerator

WAIT_FOREVER = "import asyncio\nawait asyncio.Event().wait()"


async def _async_start_waiting_execution(client: MockHAClientWebSocket) -> None:
    """Start code that waits until it gets cancelled."""
    await client.send_json_auto_id(
        {
            "type": "debug_console/execute",
            "session_id": SESSION_ID,
            "code": WAIT_FOREVER,
        }
    )

    # Once a later command is done, the waiting execution is running.
    await async_execute(client, "1")


@pytest.mark.usefixtures("setup_integration")
async def test_session_survives_reconnect(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session outlives its connection for a while, like on a reload."""
    first_client = await hass_ws_client(hass)
    await async_execute(first_client, "answer = 42")
    await first_client.close()
    await hass.async_block_till_done()

    freezer.tick(SESSION_TIMEOUT / 2)
    async_fire_time_changed(hass)
    second_client = await hass_ws_client(hass)
    result = await async_execute(second_client, "answer")

    assert result["result"] == {"type": "number", "value": "42"}

    # The new connection keeps the session alive past the original timeout.
    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    result = await async_execute(second_client, "answer")

    assert result["result"] == {"type": "number", "value": "42"}


@pytest.mark.usefixtures("setup_integration")
async def test_session_expires(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session expires a while after its last connection closes."""
    first_client = await hass_ws_client(hass)
    await async_execute(first_client, "answer = 42")
    await first_client.close()
    await hass.async_block_till_done()

    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    second_client = await hass_ws_client(hass)
    result = await async_execute(second_client, "answer")

    assert "NameError: name 'answer' is not defined" in result["error"]


@pytest.mark.usefixtures("setup_integration")
async def test_session_shared_by_connections(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session stays while any of its connections is open."""
    first_client = await hass_ws_client(hass)
    second_client = await hass_ws_client(hass)
    await async_execute(first_client, "answer = 42")
    await async_execute(second_client, "answer")

    await first_client.close()
    await hass.async_block_till_done()

    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    result = await async_execute(second_client, "answer")

    assert result["result"] == {"type": "number", "value": "42"}


@pytest.mark.usefixtures("setup_integration")
async def test_sessions_separated(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test sessions are separated by session ID and by user."""
    client = await hass_ws_client(hass)
    await async_execute(client, "secret = 'first'")

    result = await async_send(
        client,
        {"type": "debug_console/execute", "session_id": "other", "code": "secret"},
    )

    assert "NameError: name 'secret' is not defined" in result["error"]

    other_user = await hass.auth.async_create_user(
        "Other admin", group_ids=["system-admin"]
    )
    refresh_token = await hass.auth.async_create_refresh_token(other_user, CLIENT_ID)
    other_client = await hass_ws_client(
        hass, hass.auth.async_create_access_token(refresh_token)
    )
    result = await async_execute(other_client, "secret")

    assert "NameError: name 'secret' is not defined" in result["error"]


@pytest.mark.parametrize(
    "session_id",
    [pytest.param("", id="empty"), pytest.param("x" * 65, id="too_long")],
)
async def test_invalid_session_id(
    websocket_client: MockHAClientWebSocket, session_id: str
) -> None:
    """Test the session ID is validated."""
    await websocket_client.send_json_auto_id(
        {"type": "debug_console/execute", "session_id": session_id, "code": "1"}
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_INVALID_FORMAT


async def test_object_ids_unique_per_session(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test an object ID never finds an object of another session.

    Also not of a session that replaced it, after the console got enabled again.
    """
    result = await async_execute(websocket_client, "['first']")
    first_id = result["result"]["object_id"]

    # Another session tracks an object too, which could get the same number.
    other = await async_send(
        websocket_client,
        {"type": "debug_console/execute", "session_id": "other", "code": "['other']"},
    )

    assert other["result"]["object_id"] != first_id

    assert await hass.config_entries.async_reload(setup_integration.entry_id)
    replacement = await async_execute(websocket_client, "['replacement']")

    assert replacement["result"]["object_id"] != first_id

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/inspect",
            "session_id": SESSION_ID,
            "object_id": first_id,
        }
    )
    msg = await websocket_client.receive_json()

    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_stale_connection_keeps_new_session(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    setup_integration: MockConfigEntry,
) -> None:
    """Test a connection of a closed session does not expire its replacement."""
    first_client = await hass_ws_client(hass)
    second_client = await hass_ws_client(hass)
    await async_execute(first_client, "x = 1")
    await async_execute(second_client, "x = 1")

    # Disabling and enabling again replaces the session, which only the first
    # connection joins.
    assert await hass.config_entries.async_reload(setup_integration.entry_id)
    await async_execute(first_client, "answer = 42")

    await first_client.close()
    await second_client.close()
    await hass.async_block_till_done()

    # Coming back cancels the expiry, so nothing may expire the session.
    third_client = await hass_ws_client(hass)
    await async_execute(third_client, "answer")

    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    result = await async_execute(third_client, "answer")

    assert result["result"] == {"type": "number", "value": "42"}


async def test_disabling_stops_executions(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test disabling the console stops running code, and answers for it."""
    await _async_start_waiting_execution(websocket_client)

    assert await hass.config_entries.async_unload(setup_integration.entry_id)

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "execution_stopped"


async def test_code_disabling_the_console(
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test code that disables the console itself finishes, and so does that."""
    result = await async_execute(
        websocket_client,
        f"await hass.config_entries.async_unload({setup_integration.entry_id!r})",
    )

    assert result["result"] == {"type": "boolean", "value": True}
    assert setup_integration.state is ConfigEntryState.NOT_LOADED


async def test_disabling_stops_reporting_an_error(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test disabling the console while an error is reported stops that too."""
    reading = threading.Event()
    release = threading.Event()

    def _slow_read_sources(report: Any) -> None:
        reading.set()
        release.wait(5)

    with patch(
        "homeassistant.components.debug_console.execution._read_sources",
        _slow_read_sources,
    ):
        await websocket_client.send_json_auto_id(
            {
                "type": "debug_console/execute",
                "session_id": SESSION_ID,
                "code": "raise ValueError('nope')",
            }
        )
        assert await hass.async_add_executor_job(reading.wait, 5)

        try:
            assert await hass.config_entries.async_unload(setup_integration.entry_id)
        finally:
            release.set()

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "execution_stopped"


async def test_disabling_waits_for_cleanup(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test disabling lets cancelled code clean up, with its names available."""
    await async_execute(websocket_client, "import asyncio\ncleaned_up = []")
    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/execute",
            "session_id": SESSION_ID,
            "code": (
                "try:\n"
                "    await asyncio.Event().wait()\n"
                "finally:\n"
                "    await asyncio.sleep(0)\n"
                "    cleaned_up.append(True)\n"
            ),
        }
    )
    await async_execute(websocket_client, "1")
    (session,) = setup_integration.runtime_data.values()
    cleaned_up = session.namespace["cleaned_up"]

    assert await hass.config_entries.async_unload(setup_integration.entry_id)

    # Unloading itself waited for the cleanup, which also needed the names.
    assert cleaned_up == [True]
    assert not session.namespace


async def test_disabling_releases_sessions(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test disabling lets go of sessions, even with their connections open."""
    await async_execute(websocket_client, "data = [1]\ndata")
    sessions = setup_integration.runtime_data
    (session,) = sessions.values()
    (connection,) = session.connections

    assert await hass.config_entries.async_unload(setup_integration.entry_id)

    assert not sessions
    assert session.subscription_key not in connection.subscriptions
    assert not session.connections
    assert not session.objects
    assert not session.namespace


async def test_stopping_closes_sessions(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test sessions close when Home Assistant stops, which unloads nothing."""
    await _async_start_waiting_execution(websocket_client)
    sessions = setup_integration.runtime_data
    (session,) = sessions.values()
    (execution,) = session.executions

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert not sessions
    assert execution.cancelled()
