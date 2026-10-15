"""Tests for running code in the Debug console."""

from typing import Any
from unittest.mock import ANY, patch

import pytest

from homeassistant.core import HomeAssistant

from . import SESSION_ID, async_execute

from tests.typing import MockHAClientWebSocket


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

    assert await async_execute(websocket_client, code) == {
        "logs": [],
        "result": expected,
    }


async def test_long_string_truncated(websocket_client: MockHAClientWebSocket) -> None:
    """Test long strings are truncated."""
    with patch(
        "homeassistant.components.debug_console.inspection.MAX_STRING_LENGTH", 3
    ):
        result = await async_execute(websocket_client, "'abcdef'")

    assert result["result"] == {"type": "string", "value": "abc", "truncated": True}


async def test_print(websocket_client: MockHAClientWebSocket) -> None:
    """Test print logs strings as text and keeps objects inspectable."""
    result = await async_execute(
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
    result = await async_execute(
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
    result = await async_execute(websocket_client, code, check_complete=True)

    assert result.get("incomplete", False) is incomplete


async def test_namespace_persists(websocket_client: MockHAClientWebSocket) -> None:
    """Test variables and the last result survive between executions."""
    await async_execute(websocket_client, "answer = 41")

    result = await async_execute(websocket_client, "answer + 1")
    assert result["result"] == {"type": "number", "value": "42"}

    result = await async_execute(websocket_client, "_ * 2")
    assert result["result"] == {"type": "number", "value": "84"}


async def test_error(websocket_client: MockHAClientWebSocket) -> None:
    """Test an exception returns a traceback of the console code only."""
    result = await async_execute(
        websocket_client, "print('before')\ndef fail():\n    1 / 0\nfail()"
    )

    assert result["logs"] == [[{"type": "text", "value": "before", "truncated": False}]]
    assert result["error"].startswith("Traceback (most recent call last):\n")
    assert 'File "<console>", line 4, in <module>' in result["error"]
    assert "ZeroDivisionError: division by zero" in result["error"]
    assert "debug_console" not in result["error"]


async def test_syntax_error(websocket_client: MockHAClientWebSocket) -> None:
    """Test a syntax error is returned without a traceback."""
    result = await async_execute(websocket_client, "def")

    assert not result["error"].startswith("Traceback")
    assert "SyntaxError" in result["error"]


async def test_syntax_error_runs_nothing(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test code that fails to compile at the last expression runs nothing."""
    # A top level yield parses, but only fails when compiled.
    result = await async_execute(websocket_client, "changed = True\nyield 1")
    assert "SyntaxError" in result["error"]

    result = await async_execute(websocket_client, "'changed' in globals()")
    assert result["result"] == {"type": "boolean", "value": False}


async def test_concurrent_executions_keep_their_output(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test printing from overlapping executions goes to the right one."""
    await async_execute(
        websocket_client, "import asyncio\nfirst_may_print = asyncio.Event()"
    )

    await websocket_client.send_json_auto_id(
        {
            "type": "debug_console/execute",
            "session_id": SESSION_ID,
            "code": "await first_may_print.wait()\nprint('first')",
        }
    )
    second = await async_execute(
        websocket_client, "print('second')\nfirst_may_print.set()"
    )
    first = await websocket_client.receive_json()

    assert second["logs"] == [[{"type": "text", "value": "second", "truncated": False}]]
    assert first["result"]["logs"] == [
        [{"type": "text", "value": "first", "truncated": False}]
    ]


async def test_output_of_tasks_after_execution(
    websocket_client: MockHAClientWebSocket, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test tasks started by code print as usual once their execution is done."""
    result = await async_execute(
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

    result = await async_execute(websocket_client, "later_may_print.set()\nawait task")

    assert result["logs"] == []
    assert "late" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("code", "error"),
    [
        pytest.param("exit()", "SystemExit", id="exit"),
        pytest.param("raise SystemExit(3)", "SystemExit: 3", id="system_exit"),
        pytest.param("raise KeyboardInterrupt", "KeyboardInterrupt", id="interrupt"),
        pytest.param("raise GeneratorExit", "GeneratorExit", id="generator_exit"),
        pytest.param(
            "raise BaseException('oops')", "BaseException: oops", id="base_exception"
        ),
    ],
)
async def test_exit_does_not_stop_home_assistant(
    websocket_client: MockHAClientWebSocket, code: str, error: str
) -> None:
    """Test exceptions that stop Python are reported, not passed on."""
    result = await async_execute(websocket_client, code)
    assert error in result["error"]

    result = await async_execute(websocket_client, "1 + 1")
    assert result["result"] == {"type": "number", "value": "2"}


async def test_print_output_bounded(websocket_client: MockHAClientWebSocket) -> None:
    """Test printed text is truncated, and the number of lines is limited."""
    with (
        patch("homeassistant.components.debug_console.execution.MAX_STRING_LENGTH", 3),
        patch("homeassistant.components.debug_console.execution.MAX_LOG_LINES", 2),
    ):
        result = await async_execute(
            websocket_client, "for line in ['abcdef', 'b', 'c']:\n    print(line)\n"
        )

    assert result["logs"] == [
        [{"type": "text", "value": "abc", "truncated": True}],
        [{"type": "text", "value": "b", "truncated": False}],
    ]
    assert result["logs_truncated"] is True


@pytest.mark.parametrize(
    ("code", "text"),
    [
        pytest.param("print('a', 'b', sep=', ')", "a, b", id="sep"),
        pytest.param("print('a', end='!')", "a!", id="end"),
        pytest.param("print('a', [1], sep='-')", "a-[1]", id="object_as_text"),
    ],
)
async def test_print_formatting(
    websocket_client: MockHAClientWebSocket, code: str, text: str
) -> None:
    """Test print with another separator or end prints text, like Python does."""
    result = await async_execute(websocket_client, code)

    assert result["logs"] == [[{"type": "text", "value": text, "truncated": False}]]


async def test_cancelled_error_raised_by_code(
    websocket_client: MockHAClientWebSocket,
) -> None:
    """Test code raising CancelledError itself gets an answer, as an error."""
    result = await async_execute(
        websocket_client, "import asyncio\nraise asyncio.CancelledError"
    )

    assert "CancelledError" in result["error"]

    result = await async_execute(websocket_client, "1 + 1")

    assert result["result"] == {"type": "number", "value": "2"}
