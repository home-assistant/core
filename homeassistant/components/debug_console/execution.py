"""Run code in the Debug console, like the Python REPL does."""

import ast
import asyncio
import codeop
from contextvars import ContextVar
from dataclasses import dataclass, field
import inspect
import traceback
from types import CodeType
from typing import TYPE_CHECKING, Any

from .inspection import MAX_STRING_LENGTH, describe

if TYPE_CHECKING:
    from .session import ConsoleSession

CONSOLE_FILENAME = "<console>"

# Lines of print() output kept per execution, so a runaway loop stays bounded.
MAX_LOG_LINES = 1000


@dataclass(slots=True)
class _OutputCapture:
    """Collects what an execution prints, until the execution is done.

    Tasks started by the code inherit it; once closed, they print as usual.
    """

    logs: list[list[dict[str, Any]]] = field(default_factory=list)
    truncated: bool = False
    closed: bool = False


_OUTPUT_CAPTURE: ContextVar[_OutputCapture] = ContextVar("debug_console_output")


def is_incomplete(code: str) -> bool:
    """Return if the code needs more input, using the rules of the Python REPL."""
    compiler = codeop.CommandCompiler()
    compiler.compiler.flags |= ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    try:
        if compiler(code, CONSOLE_FILENAME, "exec") is None:
            return True
    except SyntaxError, ValueError, OverflowError:
        # Invalid code is complete; running it reports the error.
        return False

    # Like the Python REPL, an indented block continues until an empty line.
    last_line = code.rsplit("\n", 1)[-1]
    return last_line[:1].isspace() and bool(last_line.strip())


async def async_execute(session: ConsoleSession, code: str) -> dict[str, Any]:
    """Execute code in a session, returning what it printed and its result."""
    # Each execution runs in its own task, so this does not leak into others.
    capture = _OutputCapture()
    capture_token = _OUTPUT_CAPTURE.set(capture)

    execution = asyncio.current_task()
    assert execution is not None
    session.executions.add(execution)
    output: dict[str, Any] = {}
    try:
        result = await _async_execute(code, session.namespace)
    # Also the exceptions that stop Python, like exit() raises; they must not
    # reach the event loop, which would stop Home Assistant.
    except (Exception, SystemExit, KeyboardInterrupt) as err:  # noqa: BLE001
        result = None
        output["error"] = _format_exception(err)
    finally:
        session.executions.discard(execution)
        capture.closed = True
        _OUTPUT_CAPTURE.reset(capture_token)
        output["logs"] = capture.logs
        if capture.truncated:
            output["logs_truncated"] = True
        # Tasks started by the code keep the capture; not the output in it.
        capture.logs = []

    if "error" in output:
        return output

    if result is None:
        return {**output, "result": None}

    session.namespace["_"] = result
    return {**output, "result": describe(session, result)}


def console_print(
    session: ConsoleSession, *values: Any, file: Any = None, **kwargs: Any
) -> None:
    """Log values to the console, keeping objects inspectable like console.log."""
    capture = _OUTPUT_CAPTURE.get(None)
    if file is not None or capture is None or capture.closed:
        print(*values, file=file, **kwargs)
        return

    if len(capture.logs) >= MAX_LOG_LINES:
        capture.truncated = True
        return

    capture.logs.append(
        [
            {
                "type": "text",
                "value": value[:MAX_STRING_LENGTH],
                "truncated": len(value) > MAX_STRING_LENGTH,
            }
            if isinstance(value, str)
            else describe(session, value)
            for value in values
        ]
    )


async def _async_execute(code: str, namespace: dict[str, Any]) -> Any:
    """Execute code, returning the value of the last expression, like a REPL."""
    tree = ast.parse(code, CONSOLE_FILENAME, "exec")

    last_expression = None
    if tree.body and isinstance(last_statement := tree.body[-1], ast.Expr):
        tree.body.pop()
        last_expression = ast.Expression(last_statement.value)

    await _async_run(
        compile(tree, CONSOLE_FILENAME, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT),
        namespace,
    )

    if last_expression is None:
        return None

    return await _async_run(
        compile(
            last_expression,
            CONSOLE_FILENAME,
            "eval",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        ),
        namespace,
    )


async def _async_run(code_object: CodeType, namespace: dict[str, Any]) -> Any:
    """Run a compiled code object, awaiting it when it uses top level await."""
    result = eval(code_object, namespace)  # noqa: S307
    if code_object.co_flags & inspect.CO_COROUTINE:
        result = await result
    return result


def _format_exception(err: BaseException) -> str:
    """Format an exception, hiding the frames of the console machinery itself."""
    tb = err.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename != CONSOLE_FILENAME:
        tb = tb.tb_next

    return "".join(traceback.format_exception(type(err), err, tb))
