"""Tests for the Debug console websocket API."""

import asyncio
from collections.abc import Generator
from pathlib import Path
import sys
from typing import Any
from unittest.mock import ANY, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.debug_console.const import (
    DATA_CONSOLE_SESSIONS,
    DOMAIN,
    SESSION_TIMEOUT,
)
from homeassistant.components.websocket_api import (
    ERR_INVALID_FORMAT,
    ERR_NOT_ALLOWED,
    ERR_NOT_FOUND,
    ERR_UNAUTHORIZED,
    TYPE_RESULT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import CLIENT_ID, MockConfigEntry, MockUser, async_fire_time_changed
from tests.typing import MockHAClientWebSocket, WebSocketGenerator

SESSION_ID = "test-session"


async def _async_send(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> Any:
    """Send a command and return its result."""
    await websocket_client.send_json_auto_id({"session_id": SESSION_ID, **command})

    msg = await websocket_client.receive_json()
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    return msg["result"]


async def _async_execute(
    websocket_client: MockHAClientWebSocket, code: str, **kwargs: Any
) -> dict[str, Any]:
    """Execute code in the console and return the result."""
    return await _async_send(
        websocket_client, {"type": "debug_console/execute", "code": code, **kwargs}
    )


async def _async_inspect(
    websocket_client: MockHAClientWebSocket, object_id: str
) -> dict[str, Any]:
    """Inspect an object in the console and return its children."""
    return await _async_send(
        websocket_client, {"type": "debug_console/inspect", "object_id": object_id}
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("x = 1", None, id="statement"),
        pytest.param("None", None, id="none"),
        pytest.param("1 + 1", {"type": "number", "value": "2"}, id="number"),
        pytest.param("2**100", {"type": "number", "value": str(2**100)}, id="big"),
        pytest.param("float('inf')", {"type": "number", "value": "inf"}, id="infinity"),
        pytest.param("True", {"type": "boolean", "value": True}, id="boolean"),
        pytest.param(
            "'hi'",
            {"type": "string", "value": "hi", "truncated": False},
            id="string",
        ),
        pytest.param(
            "import asyncio\nawait asyncio.sleep(0, 'slept')",
            {"type": "string", "value": "slept", "truncated": False},
            id="await",
        ),
        pytest.param(
            "hass.states.get('light.kitchen').state",
            {"type": "string", "value": "on", "truncated": False},
            id="hass",
        ),
        pytest.param(
            "[1, 2, 3]",
            {
                "type": "object",
                "class": "list",
                "preview": "[1, 2, 3]",
                "object_id": ANY,
                "length": 3,
            },
            id="list",
        ),
        pytest.param(
            "object()",
            {
                "type": "object",
                "class": "object",
                "preview": ANY,
                "object_id": ANY,
            },
            id="object",
        ),
    ],
)
async def test_execute(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    code: str,
    expected: dict[str, Any] | None,
) -> None:
    """Test executing code returns a description of the last expression."""
    hass.states.async_set("light.kitchen", "on")

    assert await _async_execute(websocket_client, code) == {
        "logs": [],
        "result": expected,
    }


async def test_long_string_truncated(websocket_client: MockHAClientWebSocket) -> None:
    """Test long strings are truncated."""
    with patch(
        "homeassistant.components.debug_console.inspection.MAX_STRING_LENGTH", 3
    ):
        result = await _async_execute(websocket_client, "'abcdef'")

    assert result["result"] == {"type": "string", "value": "abc", "truncated": True}


async def test_print(websocket_client: MockHAClientWebSocket) -> None:
    """Test print logs strings as text and keeps objects inspectable."""
    result = await _async_execute(
        websocket_client, "print('hello', 42)\nprint({'a': 1})"
    )

    assert result["logs"] == [
        [
            {"type": "text", "value": "hello", "truncated": False},
            {"type": "number", "value": "42"},
        ],
        [
            {
                "type": "object",
                "class": "dict",
                "preview": "{'a': 1}",
                "object_id": ANY,
                "length": 1,
            }
        ],
    ]


async def test_print_to_file(websocket_client: MockHAClientWebSocket) -> None:
    """Test print with an explicit file writes to that file."""
    result = await _async_execute(
        websocket_client,
        "import io\nbuffer = io.StringIO()\nprint('hi', file=buffer)\nbuffer.getvalue()",
    )

    assert result["logs"] == []
    assert result["result"]["value"] == "hi\n"


@pytest.mark.parametrize(
    ("code", "incomplete"),
    [
        pytest.param("x = 1", False, id="statement"),
        pytest.param("foo(", True, id="open_bracket"),
        pytest.param("for x in []:", True, id="block_start"),
        pytest.param("for x in []:\n    pass", True, id="block_body"),
        pytest.param("for x in []:\n    pass\n", False, id="block_end"),
        pytest.param("for x in []:\n    pass\n    ", False, id="block_end_indent"),
        pytest.param("def", False, id="syntax_error"),
    ],
)
async def test_check_complete(
    websocket_client: MockHAClientWebSocket, code: str, incomplete: bool
) -> None:
    """Test incomplete code is not executed when checking for completeness."""
    result = await _async_execute(websocket_client, code, check_complete=True)

    assert result.get("incomplete", False) is incomplete


async def test_namespace_persists(websocket_client: MockHAClientWebSocket) -> None:
    """Test variables and the last result survive between executions."""
    await _async_execute(websocket_client, "answer = 41")

    result = await _async_execute(websocket_client, "answer + 1")
    assert result["result"] == {"type": "number", "value": "42"}

    result = await _async_execute(websocket_client, "_ * 2")
    assert result["result"] == {"type": "number", "value": "84"}


@pytest.mark.usefixtures("setup_integration")
async def test_session_survives_reconnect(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session outlives its connection for a while, like on a reload."""
    first_client = await hass_ws_client(hass)
    await _async_execute(first_client, "answer = 42")
    await first_client.close()
    await hass.async_block_till_done()

    freezer.tick(SESSION_TIMEOUT / 2)
    async_fire_time_changed(hass)
    second_client = await hass_ws_client(hass)
    result = await _async_execute(second_client, "answer")

    assert result["result"] == {"type": "number", "value": "42"}

    # The new connection keeps the session alive past the original timeout.
    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    result = await _async_execute(second_client, "answer")

    assert result["result"] == {"type": "number", "value": "42"}


async def test_session_expires(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session expires a while after its last connection closes."""
    await _async_execute(websocket_client, "answer = 42")
    assert len(hass.data[DATA_CONSOLE_SESSIONS]) == 1

    await websocket_client.close()
    await hass.async_block_till_done()
    assert len(hass.data[DATA_CONSOLE_SESSIONS]) == 1

    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not hass.data[DATA_CONSOLE_SESSIONS]


@pytest.mark.usefixtures("setup_integration")
async def test_session_shared_by_connections(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a session stays while any of its connections is open."""
    first_client = await hass_ws_client(hass)
    second_client = await hass_ws_client(hass)
    await _async_execute(first_client, "answer = 42")
    await _async_execute(second_client, "answer")

    await first_client.close()
    await hass.async_block_till_done()

    (session,) = hass.data[DATA_CONSOLE_SESSIONS].values()
    assert session.cancel_expiry is None


@pytest.mark.usefixtures("setup_integration")
async def test_sessions_separated(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test sessions are separated by session ID and by user."""
    client = await hass_ws_client(hass)
    await _async_execute(client, "secret = 'first'")

    result = await _async_send(
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

    result = await _async_execute(other_client, "secret")
    assert "NameError: name 'secret' is not defined" in result["error"]
    assert len(hass.data[DATA_CONSOLE_SESSIONS]) == 3


@pytest.mark.parametrize("session_id", ["", "x" * 65])
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


async def test_error(websocket_client: MockHAClientWebSocket) -> None:
    """Test an exception returns a traceback of the console code only."""
    result = await _async_execute(
        websocket_client, "print('before')\ndef fail():\n    1 / 0\nfail()"
    )

    assert result["logs"] == [[{"type": "text", "value": "before", "truncated": False}]]
    assert result["error"].startswith("Traceback (most recent call last):\n")
    assert 'File "<console>", line 4, in <module>' in result["error"]
    assert "ZeroDivisionError: division by zero" in result["error"]
    assert "debug_console" not in result["error"]


async def test_syntax_error(websocket_client: MockHAClientWebSocket) -> None:
    """Test a syntax error is returned without a traceback."""
    result = await _async_execute(websocket_client, "def")

    assert not result["error"].startswith("Traceback")
    assert "SyntaxError" in result["error"]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            "{'a': 1, 2: 'b'}",
            [
                {"key": "'a'", "value": {"type": "number", "value": "1"}},
                {
                    "key": "2",
                    "value": {"type": "string", "value": "b", "truncated": False},
                },
            ],
            id="mapping",
        ),
        pytest.param(
            "('x', None)",
            [
                {
                    "key": "0",
                    "value": {"type": "string", "value": "x", "truncated": False},
                },
                {"key": "1", "value": {"type": "none"}},
            ],
            id="sequence",
        ),
        pytest.param(
            """
class Thing:
    __slots__ = ("slotted", "__dict__")
    def __init__(self):
        self.slotted = 1
        self.plain = 2
        self._private = 3
        self.__dunder__ = 4
    @property
    def computed(self):
        raise AssertionError("Properties must not be evaluated")
    def method(self):
        pass
Thing()
""",
            [
                {"key": "_private", "value": {"type": "number", "value": "3"}},
                {"key": "computed", "getter": True},
                {"key": "plain", "value": {"type": "number", "value": "2"}},
                {"key": "slotted", "value": {"type": "number", "value": "1"}},
            ],
            id="object",
        ),
    ],
)
async def test_inspect(
    websocket_client: MockHAClientWebSocket,
    code: str,
    expected: list[dict[str, Any]],
) -> None:
    """Test inspecting the children of an object."""
    result = await _async_execute(websocket_client, code)

    assert await _async_inspect(websocket_client, result["result"]["object_id"]) == {
        "children": expected,
        "truncated": False,
    }


async def test_inspect_truncated(websocket_client: MockHAClientWebSocket) -> None:
    """Test inspecting an object with many children is truncated."""
    result = await _async_execute(websocket_client, "list(range(5))")

    with patch("homeassistant.components.debug_console.inspection.MAX_CHILDREN", 2):
        children = await _async_inspect(websocket_client, result["result"]["object_id"])

    assert len(children["children"]) == 2
    assert children["truncated"]


async def test_get_attribute(websocket_client: MockHAClientWebSocket) -> None:
    """Test evaluating a deferred property."""
    result = await _async_execute(
        websocket_client,
        """
class Thing:
    @property
    def works(self):
        return 'yes'
    @property
    def fails(self):
        raise ValueError('nope')
Thing()
""",
    )
    object_id = result["result"]["object_id"]

    assert await _async_send(
        websocket_client,
        {
            "type": "debug_console/get_attribute",
            "object_id": object_id,
            "attribute": "works",
        },
    ) == {"value": {"type": "string", "value": "yes", "truncated": False}}
    assert await _async_send(
        websocket_client,
        {
            "type": "debug_console/get_attribute",
            "object_id": object_id,
            "attribute": "fails",
        },
    ) == {"error": "ValueError: nope\n"}


@pytest.mark.parametrize(
    "command",
    [
        {"type": "debug_console/inspect", "object_id": "missing"},
        {
            "type": "debug_console/get_attribute",
            "object_id": "missing",
            "attribute": "x",
        },
    ],
)
async def test_unknown_object(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> None:
    """Test inspecting an unknown object returns an error."""
    await websocket_client.send_json_auto_id({"session_id": SESSION_ID, **command})

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_clear(websocket_client: MockHAClientWebSocket) -> None:
    """Test clearing releases tracked objects, but keeps the namespace."""
    result = await _async_execute(websocket_client, "data = [1]\ndata")

    await _async_send(websocket_client, {"type": "debug_console/clear"})

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/inspect",
            "session_id": SESSION_ID,
            "object_id": result["result"]["object_id"],
        }
    )
    msg = await websocket_client.receive_json()
    assert msg["error"]["code"] == ERR_NOT_FOUND

    result = await _async_execute(websocket_client, "data")
    assert result["result"]["preview"] == "[1]"


COMPLETION_SETUP = """
class Thing:
    alpha = 1

    def alps(self, alpha, also=None):
        pass

    @property
    def getter(self):
        raise AssertionError("Properties must not run while completing")

thing = Thing()
"""


@pytest.mark.parametrize(
    ("line", "token", "expected"),
    [
        pytest.param("", "", [], id="empty"),
        pytest.param("x = ", "", [], id="no_token"),
        pytest.param("has", "has", ["hasattr(", "hash(", "hass"], id="global"),
        pytest.param(
            "print(thing.al",
            "thing.al",
            ["thing.alpha", "thing.alps("],
            id="attribute",
        ),
        pytest.param("import jso", "jso", ["json"], id="import"),
        pytest.param(
            "import os, email.mi", "email.mi", ["email.mime"], id="import_submodule"
        ),
        pytest.param("from email.mi", "email.mi", ["email.mime"], id="from_module"),
        pytest.param("import email._", "email._", ["email._parseaddr"], id="private"),
        pytest.param("import doesnotexist.x", "doesnotexist.x", [], id="missing"),
        pytest.param("import json.x", "json.x", [], id="not_a_package"),
        pytest.param("from json import du", "du", ["dump", "dumps"], id="from_name"),
        pytest.param(
            "from email import (charset, mi", "mi", ["mime"], id="from_submodule"
        ),
        pytest.param("from doesnotexist import x", "x", [], id="from_missing"),
        pytest.param(
            "thing.alps(1, al",
            "al",
            ["alpha=", "also=", "all("],
            id="keyword_argument",
        ),
        pytest.param("thing.alps(also=al", "al", ["all("], id="keyword_value"),
        pytest.param("thing.ge", "thing.ge", ["thing.getter"], id="property"),
        pytest.param("thing.getter.up", "thing.getter.up", [], id="through_property"),
    ],
)
async def test_complete(
    websocket_client: MockHAClientWebSocket,
    line: str,
    token: str,
    expected: list[str],
) -> None:
    """Test completing names, attributes, and imports."""
    await _async_execute(
        websocket_client,
        COMPLETION_SETUP,
    )

    result = await _async_send(
        websocket_client, {"type": "debug_console/complete", "code": line}
    )

    assert result["token"] == token
    # Module completions depend on what is installed, so check for a subset.
    assert set(expected) <= set(result["matches"])
    assert bool(result["matches"]) == bool(expected)


@pytest.mark.parametrize(
    "command",
    [
        {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"},
        {"type": "debug_console/inspect", "session_id": SESSION_ID, "object_id": "x"},
        {
            "type": "debug_console/get_attribute",
            "session_id": SESSION_ID,
            "object_id": "x",
            "attribute": "x",
        },
        {"type": "debug_console/complete", "session_id": SESSION_ID, "code": "x"},
        {"type": "debug_console/signature", "session_id": SESSION_ID, "code": "x("},
        {"type": "debug_console/clear", "session_id": SESSION_ID},
        {"type": "debug_console/info"},
        {"type": "debug_console/warning/accept"},
    ],
)
async def test_requires_admin(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    command: dict[str, Any],
) -> None:
    """Test the console is only available to administrators."""
    hass_admin_user.groups = []

    await websocket_client.send_json_auto_id(command)

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_UNAUTHORIZED


SIGNATURE_SETUP = """
class Thing:
    def method(self, entity_id: str, *values: int, force: bool = False, **extra) -> str:
        \"\"\"Do the thing.

        In more detail.
        \"\"\"

    @property
    def getter(self):
        raise AssertionError("Properties must not be evaluated")

thing = Thing()
"""

METHOD_SIGNATURE = {
    "name": "method",
    "parameters": [
        "entity_id: str",
        "*values: int",
        "force: bool = False",
        "**extra",
    ],
    "returns": "str",
    "doc": "Do the thing.",
}


@pytest.mark.parametrize(
    ("code", "signature"),
    [
        pytest.param("thing.method(", {**METHOD_SIGNATURE, "active": 0}, id="first"),
        pytest.param(
            "thing.method('a, (b', ", {**METHOD_SIGNATURE, "active": 1}, id="string"
        ),
        pytest.param(
            "thing.method(\n    'a',\n    1,\n    2,\n",
            {**METHOD_SIGNATURE, "active": 1},
            id="var_positional",
        ),
        pytest.param(
            "thing.method('a', force=", {**METHOD_SIGNATURE, "active": 2}, id="keyword"
        ),
        pytest.param(
            "thing.method('a', other=", {**METHOD_SIGNATURE, "active": 3}, id="kwargs"
        ),
        pytest.param(
            "x = [thing.method(", {**METHOD_SIGNATURE, "active": 0}, id="nested"
        ),
        pytest.param("thing.method('a')", None, id="closed"),
        pytest.param("[1, ", None, id="not_a_call"),
        pytest.param("(1, ", None, id="parentheses"),
        pytest.param("unknown(", None, id="unknown"),
        pytest.param("thing.getter.x(", None, id="property"),
        pytest.param("thing(", None, id="not_callable"),
        pytest.param(
            "len(",
            {
                "name": "len",
                "parameters": ["obj"],
                "active": 0,
                "returns": None,
                "doc": "Return the number of items in a container.",
            },
            id="builtin",
        ),
    ],
)
async def test_signature(
    websocket_client: MockHAClientWebSocket,
    code: str,
    signature: dict[str, Any] | None,
) -> None:
    """Test the signature of the call being typed."""
    await _async_execute(websocket_client, SIGNATURE_SETUP)

    result = await _async_send(
        websocket_client, {"type": "debug_console/signature", "code": code}
    )

    assert result == {"signature": signature}


async def test_disabled_without_config_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the console refuses commands until enabled by a config entry."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"}
    )

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_ALLOWED


async def test_disabled_by_unloading(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test unloading the config entry disables the console and drops sessions."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)

    result = await _async_execute(client, "answer = 42\nanswer")
    assert result["result"] == {"type": "number", "value": "42"}
    assert hass.data[DATA_CONSOLE_SESSIONS]

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert DATA_CONSOLE_SESSIONS not in hass.data

    await client.send_json_auto_id(
        {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_ALLOWED

    # Closing the connection of a dropped session is fine.
    await client.close()
    await hass.async_block_till_done()


async def test_preview_keeps_order(websocket_client: MockHAClientWebSocket) -> None:
    """Test previews keep iteration order, instead of sorting everything."""
    result = await _async_execute(
        websocket_client, "{'b': 1, 'a': 2, **{str(i): i for i in range(10)}}"
    )

    assert (
        result["result"]["preview"] == "{'b': 1, 'a': 2, '0': 0, '1': 1, '2': 2, ...}"
    )


async def test_object_ids_unique_per_session(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test an object ID of one session never finds an object in another."""
    result = await _async_execute(websocket_client, "[1]")
    object_id = result["result"]["object_id"]

    await websocket_client.send_json_auto_id(
        {"type": "debug_console/inspect", "session_id": "other", "object_id": object_id}
    )

    msg = await websocket_client.receive_json()
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_concurrent_executions_keep_their_output(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test printing from overlapping executions goes to the right one."""
    await _async_execute(
        websocket_client, "import asyncio\nfirst_may_print = asyncio.Event()"
    )

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/execute",
            "session_id": SESSION_ID,
            "code": "await first_may_print.wait()\nprint('first')",
        }
    )
    second = await _async_execute(
        websocket_client, "print('second')\nfirst_may_print.set()"
    )
    first = await websocket_client.receive_json()

    assert second["logs"] == [[{"type": "text", "value": "second", "truncated": False}]]
    assert first["result"]["logs"] == [
        [{"type": "text", "value": "first", "truncated": False}]
    ]


async def test_executions_cancelled_when_disabled(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test disabling the console stops executions that are still running."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)
    await _async_execute(client, "import asyncio\nforever = asyncio.Event()")

    await client.send_json_auto_id(
        {
            "type": "debug_console/execute",
            "session_id": SESSION_ID,
            "code": "await forever.wait()",
        }
    )
    # Once a later command is done, the waiting execution is running.
    await _async_execute(client, "1")
    (session,) = hass.data[DATA_CONSOLE_SESSIONS].values()
    (execution,) = session.executions

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert execution.cancelled()


async def test_stale_connection_keeps_new_session(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a connection of a dropped session does not expire its replacement."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    first_client = await hass_ws_client(hass)
    second_client = await hass_ws_client(hass)
    await _async_execute(first_client, "x = 1")
    await _async_execute(second_client, "x = 1")

    # Disabling and enabling again replaces the session, which only the first
    # connection joins.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await _async_execute(first_client, "answer = 42")

    await first_client.close()
    await second_client.close()
    await hass.async_block_till_done()

    # Coming back cancels the expiry, so nothing may expire the session.
    third_client = await hass_ws_client(hass)
    await _async_execute(third_client, "answer")
    freezer.tick(SESSION_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    result = await _async_execute(third_client, "answer")
    assert result["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize(
    "command",
    [
        {"type": "debug_console/complete", "code": "trap.descriptor.x"},
        {"type": "debug_console/complete", "code": "trap.dynamic.x"},
        {"type": "debug_console/signature", "code": "trap.descriptor.x("},
        {"type": "debug_console/signature", "code": "trap.dynamic("},
        {"type": "debug_console/complete", "code": "trap.de"},
        {"type": "debug_console/signature", "code": "callable_trap("},
        {"type": "debug_console/complete", "code": "callable_trap(a"},
    ],
)
async def test_typing_runs_no_attribute_code(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> None:
    """Test completion and signatures never run user code of the objects."""
    await _async_execute(
        websocket_client,
        """
ran = []

class Descriptor:
    def __get__(self, instance, owner):
        ran.append("descriptor")

class Trap:
    descriptor = Descriptor()

    def __getattr__(self, name):
        ran.append("getattr")

    def __dir__(self):
        ran.append("dir")
        return []

class CallableTrap:
    @property
    def __signature__(self):
        ran.append("signature")

    def __call__(self, argument):
        pass

trap = Trap()
callable_trap = CallableTrap()
""",
    )

    await _async_send(websocket_client, command)
    result = await _async_execute(websocket_client, "ran")

    assert result["result"]["preview"] == "[]"


async def test_output_of_tasks_after_execution(
    websocket_client: MockHAClientWebSocket, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test tasks started by code print as usual once their execution is done."""
    result = await _async_execute(
        websocket_client,
        """
import asyncio

later_may_print = asyncio.Event()

async def later():
    await later_may_print.wait()
    print("late")

task = asyncio.ensure_future(later())
""",
    )
    assert result["logs"] == []

    result = await _async_execute(websocket_client, "later_may_print.set()\nawait task")

    assert result["logs"] == []
    assert "late" in capsys.readouterr().out


async def test_disabling_releases_sessions(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test disabling lets go of sessions, even with their connections open."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)
    await _async_execute(client, "data = [1]\ndata")
    (session,) = hass.data[DATA_CONSOLE_SESSIONS].values()
    (connection,) = session.connections

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert session.subscription_key not in connection.subscriptions
    assert not session.connections
    assert not session.objects
    assert not session.namespace


@pytest.mark.parametrize(
    ("code", "error"),
    [
        pytest.param("exit()", "SystemExit", id="exit"),
        pytest.param("raise SystemExit(3)", "SystemExit: 3", id="system_exit"),
        pytest.param("raise KeyboardInterrupt", "KeyboardInterrupt", id="interrupt"),
    ],
)
async def test_exit_does_not_stop_home_assistant(
    websocket_client: MockHAClientWebSocket, code: str, error: str
) -> None:
    """Test exceptions that stop Python are reported, not passed on."""
    result = await _async_execute(websocket_client, code)
    assert error in result["error"]

    result = await _async_execute(websocket_client, "1 + 1")
    assert result["result"] == {"type": "number", "value": "2"}


async def test_property_raising_system_exit(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test a property that exits is reported, not passed on."""
    result = await _async_execute(
        websocket_client,
        "class Thing:\n    @property\n    def leave(self):\n        exit()\n\nThing()",
    )

    assert await _async_send(
        websocket_client,
        {
            "type": "debug_console/get_attribute",
            "object_id": result["result"]["object_id"],
            "attribute": "leave",
        },
    ) == {"error": ANY}


@pytest.fixture
def probe_package(tmp_path: Path) -> Generator[str]:
    """Provide a package on the module path, that must not get imported."""
    package = tmp_path / "debug_console_probe"
    (package / "submodule").mkdir(parents=True)
    (package / "__init__.py").write_text("raise AssertionError('imported')\n")
    (package / "submodule" / "__init__.py").write_text("")
    with patch.object(sys, "path", [str(tmp_path), *sys.path]):
        yield "debug_console_probe"
    assert "debug_console_probe" not in sys.modules


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            "import debug_console_probe.sub",
            ["debug_console_probe.submodule"],
            id="import",
        ),
        pytest.param(
            "from debug_console_probe import sub", ["submodule"], id="from_import"
        ),
    ],
)
@pytest.mark.usefixtures("probe_package")
async def test_import_completion_does_not_import(
    websocket_client: MockHAClientWebSocket, code: str, expected: list[str]
) -> None:
    """Test completing imports lists modules without running their code."""
    result = await _async_send(
        websocket_client, {"type": "debug_console/complete", "code": code}
    )

    assert result["matches"] == expected


async def test_inspect_slot_replaced_by_property(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test a property replacing an inherited slot only runs on request."""
    result = await _async_execute(
        websocket_client,
        """
class Base:
    __slots__ = ("state",)

class Thing(Base):
    @property
    def state(self):
        raise AssertionError("Properties must not be evaluated")

Thing()
""",
    )

    assert await _async_inspect(websocket_client, result["result"]["object_id"]) == {
        "children": [{"key": "state", "getter": True}],
        "truncated": False,
    }


async def test_preview_of_large_bytes(websocket_client: MockHAClientWebSocket) -> None:
    """Test previews of large bytes only represent the start."""
    result = await _async_execute(websocket_client, "b'x' * 1_000_000")

    assert result["result"]["preview"] == f"b'{'x' * 80}...'"


async def test_tracked_objects(
    hass: HomeAssistant, websocket_client: MockHAClientWebSocket
) -> None:
    """Test objects are tracked once, and the oldest are let go."""
    first = await _async_execute(websocket_client, "data = [1]\ndata")
    again = await _async_execute(websocket_client, "data")
    assert first["result"]["object_id"] == again["result"]["object_id"]

    with patch("homeassistant.components.debug_console.session.MAX_TRACKED_OBJECTS", 2):
        await _async_execute(websocket_client, "[2]")
        await _async_execute(websocket_client, "[3]")

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/inspect",
            "session_id": SESSION_ID,
            "object_id": first["result"]["object_id"],
        }
    )
    msg = await websocket_client.receive_json()
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_print_output_bounded(websocket_client: MockHAClientWebSocket) -> None:
    """Test printed text is truncated, and the number of lines is limited."""
    with (
        patch("homeassistant.components.debug_console.execution.MAX_STRING_LENGTH", 3),
        patch("homeassistant.components.debug_console.execution.MAX_LOG_LINES", 2),
    ):
        result = await _async_execute(
            websocket_client, "for line in ['abcdef', 'b', 'c']:\n    print(line)\n"
        )

    assert result["logs"] == [
        [{"type": "text", "value": "abc", "truncated": True}],
        [{"type": "text", "value": "b", "truncated": False}],
    ]
    assert result["logs_truncated"] is True


async def test_cancelled_code_cleans_up_when_disabled(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test cancelled code can still use its names while cleaning up."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    client = await hass_ws_client(hass)
    await _async_execute(client, "import asyncio\ncleaned_up = asyncio.Event()")

    await client.send_json_auto_id(
        {
            "type": "debug_console/execute",
            "session_id": SESSION_ID,
            "code": "try:\n    await asyncio.Event().wait()\nfinally:\n    cleaned_up.set()\n",
        }
    )
    # Once a later command is done, the waiting execution is running.
    await _async_execute(client, "1")
    (session,) = hass.data[DATA_CONSOLE_SESSIONS].values()
    (execution,) = session.executions
    cleaned_up = session.namespace["cleaned_up"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    # Executions run as background tasks, which block_till_done does not await.
    await asyncio.wait([execution])

    assert cleaned_up.is_set()
    assert not session.namespace
