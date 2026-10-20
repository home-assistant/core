"""Tests for the sessions of the Debug console."""

import threading
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import CLIENT_ID, async_fire_time_changed
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components.debug_console.const import SESSION_TIMEOUT
from homeassistant.components.debug_console.session import DATA_SESSIONS
from homeassistant.components.websocket_api import ERR_INVALID_FORMAT, ERR_NOT_FOUND
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import SESSION_ID, async_execute, async_send

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


async def test_stop(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test stopping the code a session runs, while the console stays usable."""
    await _async_start_waiting_execution(websocket_client)
    (session,) = hass.data[DATA_SESSIONS].values()
    (execution,) = session.executions

    await websocket_client.send_json_auto_id(
        {"type": "debug_console/stop", "session_id": SESSION_ID}
    )
    responses = {
        msg["id"]: msg
        for msg in (
            await websocket_client.receive_json(),
            await websocket_client.receive_json(),
        )
    }
    await hass.async_block_till_done()

    assert execution.cancelled()
    stopped, done = (responses[msg_id] for msg_id in sorted(responses))
    assert stopped["error"]["code"] == "execution_stopped"
    assert done["success"]

    result = await async_execute(websocket_client, "1 + 1")
    assert result["result"] == {"type": "number", "value": "2"}


async def test_stop_without_session(websocket_client: MockHAClientWebSocket) -> None:
    """Test stopping a session that does not exist does nothing."""
    result = await async_send(websocket_client, {"type": "debug_console/stop"})

    assert result is None


async def _async_stop(hass: HomeAssistant) -> None:
    """Stop Home Assistant, as far as the console sees it."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


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
    await other_client.send_json_auto_id({"type": "debug_console/warning/accept"})
    assert (await other_client.receive_json())["success"]
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


@pytest.mark.usefixtures("setup_integration")
async def test_object_ids_unique_per_session(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an object ID never finds an object of another session.

    Also not of a session that replaced it, after it expired.
    """
    first_client = await hass_ws_client(hass)
    result = await async_execute(first_client, "['first']")
    first_id = result["result"]["object_id"]

    # Another session tracks an object too, which could get the same number.
    other = await async_send(
        first_client,
        {"type": "debug_console/execute", "session_id": "other", "code": "['other']"},
    )

    assert other["result"]["object_id"] != first_id

    await first_client.close()
    await hass.async_block_till_done()
    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    websocket_client = await hass_ws_client(hass)
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


async def test_stopping_stops_reporting_an_error(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test stopping Home Assistant while an error is reported stops that too."""
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
        (session,) = hass.data[DATA_SESSIONS].values()
        (execution,) = session.executions

        try:
            await _async_stop(hass)
        finally:
            release.set()

    assert execution.cancelled()


async def test_stopping_waits_for_cleanup(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test stopping lets cancelled code clean up, with its names available."""
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
    (session,) = hass.data[DATA_SESSIONS].values()
    cleaned_up = session.namespace["cleaned_up"]

    await _async_stop(hass)

    # Stopping waited for the cleanup, which also needed the names.
    assert cleaned_up == [True]
    assert not session.namespace


async def test_stopping_releases_sessions(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test stopping lets go of sessions, even with their connections open."""
    await async_execute(websocket_client, "data = [1]\ndata")
    sessions = hass.data[DATA_SESSIONS]
    (session,) = sessions.values()
    (connection,) = session.connections

    await _async_stop(hass)

    assert not sessions
    assert session.subscription_key not in connection.subscriptions
    assert not session.connections
    assert not session.objects
    assert not session.namespace


async def test_stopping_closes_sessions(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test sessions close when Home Assistant stops."""
    await _async_start_waiting_execution(websocket_client)
    sessions = hass.data[DATA_SESSIONS]
    (session,) = sessions.values()
    (execution,) = session.executions

    await _async_stop(hass)

    assert not sessions
    assert execution.cancelled()
