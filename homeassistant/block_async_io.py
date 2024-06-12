"""Block blocking calls being done in asyncio."""

import builtins
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import glob
from http.client import HTTPConnection
import importlib
import os
import sys
import threading
import time
from types import ModuleType
from typing import Any

from .helpers.frame import get_current_frame
from .util.loop import protect_loop

_IN_TESTS = "unittest" in sys.modules

ALLOWED_FILE_PREFIXES = ("/proc",)


def _check_import_call_allowed(mapped_args: dict[str, Any]) -> bool:
    # If the module is already imported, we can ignore it.
    return bool((args := mapped_args.get("args")) and args[0] in sys.modules)


def _check_file_allowed(mapped_args: dict[str, Any]) -> bool:
    # If the file is in /proc we can ignore it.
    args = mapped_args["args"]
    path = args[0] if type(args[0]) is str else str(args[0])  # noqa: E721
    return path.startswith(ALLOWED_FILE_PREFIXES)


def _check_sleep_call_allowed(mapped_args: dict[str, Any]) -> bool:
    #
    # Avoid extracting the stack unless we need to since it
    # will have to access the linecache which can do blocking
    # I/O and we are trying to avoid blocking calls.
    #
    # frame[0] is us
    # frame[1] is raise_for_blocking_call
    # frame[2] is protected_loop_func
    # frame[3] is the offender
    with suppress(ValueError):
        return get_current_frame(4).f_code.co_filename.endswith("pydevd.py")
    return False


@dataclass(slots=True, frozen=True)
class BlockingCall:
    """Class to hold information about a blocking call."""

    original_func: Callable
    module: ModuleType
    function: str
    check_allowed: Callable[[dict[str, Any]], bool] | None
    strict: bool
    strict_core: bool
    skip_for_tests: bool


BLOCKING_CALLS: tuple[BlockingCall, ...] = (
    BlockingCall(
        original_func=HTTPConnection.putrequest,
        module=HTTPConnection,  # type: ignore[arg-type]
        function="putrequest",
        check_allowed=None,
        strict=True,
        strict_core=True,
        skip_for_tests=False,
    ),
    BlockingCall(
        original_func=time.sleep,
        module=time,
        function="sleep",
        check_allowed=_check_sleep_call_allowed,
        strict=True,
        strict_core=True,
        skip_for_tests=False,
    ),
    BlockingCall(
        original_func=glob.glob,
        module=glob,
        function="glob",
        check_allowed=None,
        strict=False,
        strict_core=False,
        skip_for_tests=False,
    ),
    BlockingCall(
        original_func=glob.iglob,
        module=glob,
        function="iglob",
        check_allowed=None,
        strict=False,
        strict_core=False,
        skip_for_tests=False,
    ),
    BlockingCall(
        original_func=os.walk,
        module=os,
        function="walk",
        check_allowed=None,
        strict=False,
        strict_core=False,
        skip_for_tests=False,
    ),
    BlockingCall(
        original_func=os.listdir,
        module=os,
        function="listdir",
        check_allowed=None,
        strict=False,
        strict_core=False,
        skip_for_tests=True,
    ),
    BlockingCall(
        original_func=os.scandir,
        module=os,
        function="scandir",
        check_allowed=None,
        strict=False,
        strict_core=False,
        skip_for_tests=True,
    ),
    BlockingCall(
        original_func=builtins.open,
        module=builtins,
        function="open",
        check_allowed=_check_file_allowed,
        strict=False,
        strict_core=False,
        skip_for_tests=True,
    ),
    BlockingCall(
        original_func=importlib.import_module,
        module=importlib,
        function="import_module",
        check_allowed=_check_import_call_allowed,
        strict=False,
        strict_core=False,
        skip_for_tests=True,
    ),
)


@dataclass(slots=True)
class BlockedCalls:
    """Class to track which calls are blocked."""

    calls: set[BlockingCall]


_BLOCKED_CALLS = BlockedCalls(set())


def enable() -> None:
    """Enable the detection of blocking calls in the event loop."""
    if _BLOCKED_CALLS.calls:
        return

    loop_thread_id = threading.get_ident()
    for blocking_call in BLOCKING_CALLS:
        if _IN_TESTS and blocking_call.skip_for_tests:
            continue

        protected_function = protect_loop(
            blocking_call.original_func,
            strict=blocking_call.strict,
            strict_core=blocking_call.strict_core,
            check_allowed=blocking_call.check_allowed,
            loop_thread_id=loop_thread_id,
        )
        setattr(blocking_call.module, blocking_call.function, protected_function)
        _BLOCKED_CALLS.calls.add(blocking_call)


def disable() -> None:
    """Disable the detection of blocking calls in the event loop."""
    for blocking_call in _BLOCKED_CALLS.calls:
        setattr(
            blocking_call.module, blocking_call.function, blocking_call.original_func
        )
    _BLOCKED_CALLS.calls.clear()
