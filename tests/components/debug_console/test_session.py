"""Tests for the sessions of the Debug console."""

import asyncio
from collections.abc import Awaitable, Callable
import threading
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components.debug_console.const import SESSION_TIMEOUT
from homeassistant.components.debug_console.execution import (
    async_execute as async_execute_code,
)
from homeassistant.components.debug_console.session import (
    DATA_LLM_SESSIONS,
    DATA_MCP_SESSIONS,
    DATA_SESSIONS,
    SessionNotFoundError,
    async_close_agent_sessions,
    async_llm_session,
    async_mcp_session,
)
from homeassistant.components.websocket_api import ERR_INVALID_FORMAT, ERR_NOT_FOUND
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import SESSION_ID, async_execute, async_send

WAIT_FOREVER = "import asyncio\nawait asyncio.Event().wait()"
MCP_USER_ID = "first-user"
MCP_CREDENTIAL_ID = "first-credential"


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
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    frontend_ws_client: WebSocketGenerator,
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
    other_client = await frontend_ws_client(other_user)
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


@pytest.mark.usefixtures("setup_integration")
async def test_mcp_namespace_persists(hass: HomeAssistant) -> None:
    """Test an issued MCP handle resumes its namespace and print capture."""
    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID) as first:
        await async_execute_code(hass, first, "answer = 41")

    async with async_mcp_session(
        hass, MCP_USER_ID, MCP_CREDENTIAL_ID, first.session_id
    ) as second:
        assert second is first
        assert second.namespace["hass"] is hass
        result = await async_execute_code(hass, second, "print(answer)\nanswer + 1")

    assert result == {
        "logs": [[{"type": "number", "value": "41"}]],
        "result": {"type": "number", "value": "42"},
    }


@pytest.mark.usefixtures("setup_integration")
async def test_mcp_omitting_handle_creates_new_session(hass: HomeAssistant) -> None:
    """Test each omitted handle issues a distinct session even for one credential."""
    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID) as first:
        await async_execute_code(hass, first, "secret = 42")

    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID) as second:
        result = await async_execute_code(hass, second, "secret")

    assert second is not first
    assert second.session_id != first.session_id
    assert len(first.session_id) == len(second.session_id) == 32
    assert "NameError: name 'secret' is not defined" in result["error"]


@pytest.mark.parametrize(
    ("user_id", "credential_id"),
    [
        pytest.param("second-user", MCP_CREDENTIAL_ID, id="other-user"),
        pytest.param(MCP_USER_ID, "second-credential", id="other-credential"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_mcp_foreign_handles_rejected(
    hass: HomeAssistant, user_id: str, credential_id: str
) -> None:
    """Test foreign handle lookups neither create sessions nor refresh expiry."""
    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID) as session:
        await async_execute_code(hass, session, "secret = 42")
    cancel_expiry = session.cancel_expiry

    with pytest.raises(SessionNotFoundError):
        async with async_mcp_session(hass, user_id, credential_id, session.session_id):
            pytest.fail("A foreign handle resumed the session")

    assert list(hass.data[DATA_MCP_SESSIONS].values()) == [session]
    assert session.cancel_expiry is cancel_expiry
    assert session.namespace["secret"] == 42


@pytest.mark.usefixtures("setup_integration")
async def test_mcp_unknown_handle_does_not_create_session(hass: HomeAssistant) -> None:
    """Test arbitrary caller handles cannot create a namespace."""
    with pytest.raises(SessionNotFoundError):
        async with async_mcp_session(
            hass, MCP_USER_ID, MCP_CREDENTIAL_ID, "unknown-handle"
        ):
            pytest.fail("An unknown handle created a session")

    assert not hass.data[DATA_MCP_SESSIONS]


@pytest.mark.usefixtures("setup_integration")
async def test_agent_registries_isolated(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test browser, MCP and local agent namespaces remain separate."""
    await async_execute(websocket_client, "browser_secret = 42")

    async with async_mcp_session(
        hass, hass_admin_user.id, MCP_CREDENTIAL_ID
    ) as mcp_session:
        await async_execute_code(hass, mcp_session, "agent_secret = 41")
        result = await async_execute_code(hass, mcp_session, "browser_secret")

    assert "NameError: name 'browser_secret' is not defined" in result["error"]
    result = await async_execute(websocket_client, "agent_secret")
    assert "NameError: name 'agent_secret' is not defined" in result["error"]

    async with async_llm_session(
        hass, hass_admin_user.id, "test", "agent", mcp_session.session_id
    ) as local_session:
        result = await async_execute_code(hass, local_session, "agent_secret")

    assert "NameError: name 'agent_secret' is not defined" in result["error"]
    assert local_session is not mcp_session


@pytest.mark.usefixtures("setup_integration")
async def test_mcp_idle_session_expires(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test idle expiry removes a handle and subsequent use cannot recreate it."""
    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID) as session:
        await async_execute_code(hass, session, "answer = 42")

    freezer.tick(SESSION_TIMEOUT / 2)
    async_fire_time_changed(hass)
    async with async_mcp_session(
        hass, MCP_USER_ID, MCP_CREDENTIAL_ID, session.session_id
    ) as resumed:
        assert resumed is session

    freezer.tick(SESSION_TIMEOUT / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.data[DATA_MCP_SESSIONS][MCP_USER_ID, MCP_CREDENTIAL_ID, session.session_id]
        is session
    )

    freezer.tick(SESSION_TIMEOUT / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not hass.data[DATA_MCP_SESSIONS]
    assert not session.namespace

    with pytest.raises(SessionNotFoundError):
        async with async_mcp_session(
            hass, MCP_USER_ID, MCP_CREDENTIAL_ID, session.session_id
        ):
            pytest.fail("An expired handle recreated its session")

    assert not hass.data[DATA_MCP_SESSIONS]


async def _async_mcp_waiting_execution(
    hass: HomeAssistant,
    started: asyncio.Event,
    release: asyncio.Event,
    cleaned_up: list[bool],
) -> None:
    """Run code until it is released or its session closes."""
    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID) as session:
        session.namespace.update(
            started=started, release=release, cleaned_up=cleaned_up
        )
        await async_execute_code(
            hass,
            session,
            "import asyncio\n"
            "try:\n"
            "    started.set()\n"
            "    await release.wait()\n"
            "finally:\n"
            "    await asyncio.sleep(0)\n"
            "    cleaned_up.append(True)\n",
        )


@pytest.mark.usefixtures("setup_integration")
async def test_mcp_active_requests_do_not_expire(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test overlapping requests keep a session alive until the last one ends."""
    started = asyncio.Event()
    release = asyncio.Event()
    execution = asyncio.create_task(
        _async_mcp_waiting_execution(hass, started, release, [])
    )
    await started.wait()
    (session,) = hass.data[DATA_MCP_SESSIONS].values()

    async with async_mcp_session(
        hass, MCP_USER_ID, MCP_CREDENTIAL_ID, session.session_id
    ) as concurrent:
        assert concurrent is session

    freezer.tick(SESSION_TIMEOUT * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert list(hass.data[DATA_MCP_SESSIONS].values()) == [session]
    assert session.cancel_expiry is None

    release.set()
    await execution
    assert session.cancel_expiry is not None

    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not hass.data[DATA_MCP_SESSIONS]


async def _async_close_user_agent_sessions(hass: HomeAssistant, user_id: str) -> None:
    """Close the user's MCP and local agent sessions."""
    async_close_agent_sessions(hass, user_id)


async def _async_agent_shutdown(hass: HomeAssistant, _user_id: str) -> None:
    """Stop Home Assistant's console sessions."""
    await _async_stop(hass)


@pytest.mark.parametrize(
    "close_sessions",
    [
        pytest.param(_async_close_user_agent_sessions, id="user-removed"),
        pytest.param(_async_agent_shutdown, id="shutdown"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_agent_closing_cancels_execution(
    hass: HomeAssistant,
    close_sessions: Callable[[HomeAssistant, str], Awaitable[None]],
) -> None:
    """Test closure clears both registries and lets cancelled code clean up."""
    async with async_llm_session(
        hass, MCP_USER_ID, "test", None, "conversation"
    ) as local_session:
        await async_execute_code(hass, local_session, "local_secret = 1")
    started = asyncio.Event()
    cleaned_up: list[bool] = []
    execution = asyncio.create_task(
        _async_mcp_waiting_execution(hass, started, asyncio.Event(), cleaned_up)
    )
    await started.wait()
    (session,) = hass.data[DATA_MCP_SESSIONS].values()

    await close_sessions(hass, MCP_USER_ID)
    with pytest.raises(asyncio.CancelledError):
        await execution
    await hass.async_block_till_done()

    assert cleaned_up == [True]
    assert not hass.data[DATA_MCP_SESSIONS]
    assert not hass.data[DATA_LLM_SESSIONS]
    assert not session.namespace
    assert not local_session.namespace
    assert session.cancel_expiry is None
    assert local_session.cancel_expiry is None


@pytest.mark.usefixtures("setup_integration")
async def test_agent_closing_keeps_other_users_sessions(hass: HomeAssistant) -> None:
    """Test removing one user leaves other users' sessions available."""
    async with async_mcp_session(hass, MCP_USER_ID, MCP_CREDENTIAL_ID):
        pass
    async with async_mcp_session(hass, "second-user", MCP_CREDENTIAL_ID) as other:
        await async_execute_code(hass, other, "answer = 42")
    async with async_llm_session(hass, MCP_USER_ID, "test", None, "conversation"):
        pass
    async with async_llm_session(
        hass, "second-user", "test", None, "conversation"
    ) as other_local:
        await async_execute_code(hass, other_local, "answer = 41")

    async_close_agent_sessions(hass, MCP_USER_ID)

    assert list(hass.data[DATA_MCP_SESSIONS].values()) == [other]
    assert list(hass.data[DATA_LLM_SESSIONS].values()) == [other_local]
    assert other.namespace["answer"] == 42
    assert other_local.namespace["answer"] == 41
