"""Run code in the Debug console, like the Python REPL does."""

import ast
import asyncio
import codeop
from contextvars import ContextVar
from dataclasses import dataclass, field
import inspect
import io
import linecache
import traceback
from types import CodeType
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .inspection import MAX_STRING_LENGTH, USER_CODE_ERRORS, class_name, describe

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

_EXCEPTION_TRACEBACK = vars(BaseException)["__traceback__"]

# Statements with an indented block, which the Python REPL ends at an empty line.
_COMPOUND_STATEMENTS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)


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
    # Only a block: the last line of a call can be indented too.
    last_line = code.rsplit("\n", 1)[-1]
    if not last_line[:1].isspace() or not last_line.strip():
        return False

    statements = ast.parse(code, CONSOLE_FILENAME, "exec").body
    return bool(statements) and isinstance(statements[-1], _COMPOUND_STATEMENTS)


async def async_execute(
    hass: HomeAssistant, session: ConsoleSession, code: str
) -> dict[str, Any]:
    """Execute code in a session, returning what it printed and its result."""
    execution = asyncio.current_task()
    assert execution is not None

    # Until it is reported too, as reporting an error runs code of it, which
    # has to stop when the console does.
    session.executions.add(execution)
    try:
        return await _async_execute_and_report(hass, session, code, execution)
    finally:
        session.executions.discard(execution)


async def _async_execute_and_report(
    hass: HomeAssistant,
    session: ConsoleSession,
    code: str,
    execution: asyncio.Task[Any],
) -> dict[str, Any]:
    """Execute code, and report what it printed and its result or error."""
    # Each execution runs in its own task, so this does not leak into others.
    capture = _OutputCapture()
    capture_token = _OUTPUT_CAPTURE.set(capture)

    error: BaseException | None = None
    description: dict[str, Any] | None = None
    try:
        result = await _async_execute(code, session.namespace)
        if result is not None:
            session.namespace["_"] = result
            # Describing runs code of the result too, like its __repr__.
            description = describe(session, result)
    except asyncio.CancelledError as err:
        # Raised by the code itself; when the execution got cancelled, it stops.
        if execution.cancelling():
            raise

        error = err
    except USER_CODE_ERRORS as err:
        error = err
    finally:
        capture.closed = True
        _OUTPUT_CAPTURE.reset(capture_token)

        # Tasks started by the code keep the capture, not the output in it.
        logs = capture.logs
        capture.logs = []

    output: dict[str, Any] = {"logs": logs}
    if capture.truncated:
        output["logs_truncated"] = True

    if error is not None:
        output["error"] = await _async_format_exception(hass, error)
        return output

    return {**output, "result": description}


def console_print(
    session: ConsoleSession,
    *values: Any,
    sep: str | None = " ",
    end: str | None = "\n",
    file: Any = None,
    flush: bool = False,
) -> None:
    """Log values to the console, keeping objects inspectable like console.log.

    With another separator or line end, the line is text, formatted by print.
    """
    capture = _OUTPUT_CAPTURE.get(None)
    if file is not None or capture is None or capture.closed:
        print(*values, sep=sep, end=end, file=file, flush=flush)
        return

    if len(capture.logs) >= MAX_LOG_LINES:
        capture.truncated = True
        return

    if sep not in (" ", None) or end not in ("\n", None):
        text = io.StringIO()
        print(*values, sep=sep, end=end, file=text)
        capture.logs.append([_describe_text(text.getvalue().removesuffix("\n"))])
        return

    capture.logs.append(
        [
            _describe_text(value) if type(value) is str else describe(session, value)
            for value in values
        ]
    )


def _describe_text(text: str) -> dict[str, Any]:
    """Describe printed text, which shows as is."""
    return {
        "type": "text",
        "value": text[:MAX_STRING_LENGTH],
        "truncated": len(text) > MAX_STRING_LENGTH,
    }


async def _async_execute(code: str, namespace: dict[str, Any]) -> Any:
    """Execute code, returning the value of the last expression, like a REPL."""
    tree = ast.parse(code, CONSOLE_FILENAME, "exec")

    last_expression = None
    if tree.body and isinstance(last_statement := tree.body[-1], ast.Expr):
        tree.body.pop()
        last_expression = ast.Expression(last_statement.value)

    # Compile both first, so code that does not compile changes nothing.
    statements = compile(
        tree, CONSOLE_FILENAME, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    )
    expression = None
    if last_expression is not None:
        expression = compile(
            last_expression,
            CONSOLE_FILENAME,
            "eval",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )

    await _async_run(statements, namespace)

    if expression is None:
        return None

    return await _async_run(expression, namespace)


async def _async_run(code_object: CodeType, namespace: dict[str, Any]) -> Any:
    """Run a compiled code object, awaiting it when it uses top level await."""
    result = eval(code_object, namespace)  # noqa: S307
    if code_object.co_flags & inspect.CO_COROUTINE:
        result = await result

    return result


async def _async_format_exception(hass: HomeAssistant, err: BaseException) -> str:
    """Format an exception with its traceback, like Python does.

    Capturing and formatting it runs code of the exception, like its __str__
    and __notes__, which can raise too. That stays in the event loop; only
    reading the source of its frames from disk happens in the executor.
    """
    try:
        report = _capture_exception(err)
    except USER_CODE_ERRORS:
        return f"<{class_name(err)} that failed to format>"

    await hass.async_add_executor_job(_read_sources, report)

    try:
        return "".join(report.format())
    except USER_CODE_ERRORS:
        return f"<{class_name(err)} that failed to format>"


def _read_sources(report: traceback.TracebackException) -> None:
    """Read the source of each frame in a report, and the reports it chains.

    From disk only. Capturing registers a loader of the module of each frame,
    which can be code of the user, to get the source from on request.
    """
    reports = [report]
    while reports:
        current = reports.pop()
        for frame in current.stack:
            # A registered loader is cached as a tuple of just its getter.
            if len(linecache.cache.get(frame.filename, ())) == 1:
                linecache.cache.pop(frame.filename, None)

            linecache.getlines(frame.filename)

        reports.extend(
            chained
            for chained in (current.__cause__, current.__context__)
            if chained is not None
        )
        reports.extend(current.exceptions or ())


def _capture_exception(err: BaseException) -> traceback.TracebackException:
    """Capture an exception to report, hiding the frames of the console itself."""
    # Its own traceback, as an exception can replace __traceback__ too.
    tb = _EXCEPTION_TRACEBACK.__get__(err)  # pylint: disable=unnecessary-dunder-call
    while tb is not None and tb.tb_frame.f_code.co_filename != CONSOLE_FILENAME:
        tb = tb.tb_next

    return traceback.TracebackException(type(err), err, tb, lookup_lines=False)
