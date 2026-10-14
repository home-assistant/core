"""Tests for describing and inspecting values in the Debug console."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.websocket_api import ERR_NOT_FOUND

from . import SESSION_ID, async_execute, async_inspect, async_send

from tests.typing import MockHAClientWebSocket


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
    result = await async_execute(websocket_client, code)

    assert await async_inspect(websocket_client, result["result"]["object_id"]) == {
        "children": expected,
        "truncated": False,
    }


async def test_inspect_truncated(websocket_client: MockHAClientWebSocket) -> None:
    """Test inspecting an object with many children is truncated."""
    result = await async_execute(websocket_client, "list(range(5))")

    with patch("homeassistant.components.debug_console.inspection.MAX_CHILDREN", 2):
        children = await async_inspect(websocket_client, result["result"]["object_id"])

    assert len(children["children"]) == 2
    assert children["truncated"]


async def test_get_attribute(websocket_client: MockHAClientWebSocket) -> None:
    """Test evaluating a deferred property."""
    result = await async_execute(
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

    assert await async_send(
        websocket_client,
        {
            "type": "debug_console/get_attribute",
            "object_id": object_id,
            "attribute": "works",
        },
    ) == {"value": {"type": "string", "value": "yes", "truncated": False}}
    assert await async_send(
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
    result = await async_execute(websocket_client, "data = [1]\ndata")

    await async_send(websocket_client, {"type": "debug_console/clear"})

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/inspect",
            "session_id": SESSION_ID,
            "object_id": result["result"]["object_id"],
        }
    )
    msg = await websocket_client.receive_json()
    assert msg["error"]["code"] == ERR_NOT_FOUND

    result = await async_execute(websocket_client, "data")
    assert result["result"]["preview"] == "[1]"


async def test_preview_keeps_order(websocket_client: MockHAClientWebSocket) -> None:
    """Test previews keep iteration order, instead of sorting everything."""
    result = await async_execute(
        websocket_client, "{'b': 1, 'a': 2, **{str(i): i for i in range(10)}}"
    )

    assert (
        result["result"]["preview"] == "{'b': 1, 'a': 2, '0': 0, '1': 1, '2': 2, ...}"
    )


async def test_property_raising_system_exit(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test a property that exits is reported, not passed on."""
    result = await async_execute(
        websocket_client,
        "class Thing:\n    @property\n    def leave(self):\n        exit()\n\nThing()",
    )

    assert await async_send(
        websocket_client,
        {
            "type": "debug_console/get_attribute",
            "object_id": result["result"]["object_id"],
            "attribute": "leave",
        },
    ) == {"error": "SystemExit: None\n"}

    result = await async_execute(websocket_client, "1 + 1")

    assert result["result"] == {"type": "number", "value": "2"}


async def test_inspect_slot_replaced_by_property(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test a property replacing an inherited slot only runs on request."""
    result = await async_execute(
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

    assert await async_inspect(websocket_client, result["result"]["object_id"]) == {
        "children": [{"key": "state", "getter": True}],
        "truncated": False,
    }


async def test_preview_of_large_bytes(websocket_client: MockHAClientWebSocket) -> None:
    """Test previews of large bytes only represent the start."""
    result = await async_execute(websocket_client, "b'x' * 1_000_000")

    assert result["result"]["preview"] == f"b'{'x' * 80}...'"


async def test_tracked_objects(websocket_client: MockHAClientWebSocket) -> None:
    """Test objects are tracked once, and the oldest are let go."""
    first = await async_execute(websocket_client, "data = [1]\ndata")
    again = await async_execute(websocket_client, "data")
    assert first["result"]["object_id"] == again["result"]["object_id"]

    with patch("homeassistant.components.debug_console.session.MAX_TRACKED_OBJECTS", 2):
        await async_execute(websocket_client, "[2]")
        await async_execute(websocket_client, "[3]")

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/inspect",
            "session_id": SESSION_ID,
            "object_id": first["result"]["object_id"],
        }
    )
    msg = await websocket_client.receive_json()
    assert msg["error"]["code"] == ERR_NOT_FOUND


@pytest.mark.parametrize(
    ("code", "preview"),
    [
        pytest.param("{}", "{}", id="empty_dict"),
        pytest.param("{'a': {'b': {'c': 1}}}", "{'a': {'b': {...}}}", id="deep_dict"),
        pytest.param("set()", "set()", id="empty_set"),
        pytest.param("{1}", "{1}", id="set"),
        pytest.param("frozenset()", "frozenset()", id="empty_frozenset"),
        pytest.param("frozenset({1})", "frozenset({1})", id="frozenset"),
        pytest.param("[[{1}]]", "[[{...}]]", id="deep_set"),
        pytest.param("b'abc'", "b'abc'", id="short_bytes"),
        pytest.param(
            "bytearray(b'x' * 100)",
            f"bytearray(b'{'x' * 80}'...)",
            id="bytearray",
        ),
    ],
)
async def test_previews(
    websocket_client: MockHAClientWebSocket, code: str, preview: str
) -> None:
    """Test previews of values the console shows."""
    result = await async_execute(websocket_client, code)

    assert result["result"]["preview"] == preview


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("object()", id="no_dict"),
        pytest.param(
            "class Thing:\n    @property\n    def __dict__(self):\n"
            "        raise AssertionError('ran')\n\nThing()",
            id="dict_property",
        ),
    ],
)
async def test_inspect_without_instance_dict(
    websocket_client: MockHAClientWebSocket, code: str
) -> None:
    """Test inspecting objects whose __dict__ is missing or not safe to read."""
    result = await async_execute(websocket_client, code)

    assert await async_inspect(websocket_client, result["result"]["object_id"]) == {
        "children": [],
        "truncated": False,
    }


async def test_preview_of_broken_repr(websocket_client: MockHAClientWebSocket) -> None:
    """Test an object with a broken __repr__ still shows, as its class."""
    result = await async_execute(
        websocket_client,
        "class Broken:\n    def __repr__(self):\n        raise ValueError\n\nBroken()",
    )

    assert result["result"]["preview"].startswith("<Broken instance at 0x")


@pytest.mark.parametrize(
    ("code", "preview", "length"),
    [
        pytest.param(
            "class Bad:\n    def __repr__(self):\n        exit()\n\nBad()",
            "<Bad that failed to represent itself>",
            None,
            id="repr",
        ),
        pytest.param(
            "class Bad(list):\n    def __len__(self):\n        exit()\n\nBad()",
            "[]",
            None,
            id="len",
        ),
    ],
)
async def test_describing_does_not_exit(
    websocket_client: MockHAClientWebSocket,
    code: str,
    preview: str,
    length: int | None,
) -> None:
    """Test values whose methods exit still show, and Home Assistant keeps going."""
    result = await async_execute(websocket_client, code)

    assert result["result"]["preview"] == preview
    assert result["result"].get("length") == length


async def test_inspecting_does_not_exit(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test a container that exits while iterating reports an error."""
    result = await async_execute(
        websocket_client,
        "class Bad(list):\n    def __iter__(self):\n        exit()\n\nBad([1])",
    )

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/inspect",
            "session_id": SESSION_ID,
            "object_id": result["result"]["object_id"],
        }
    )
    msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"] == {"code": "unknown_error", "message": "SystemExit: None"}
