"""Block blocking calls being done in asyncio."""

from contextlib import suppress
from http.client import HTTPConnection
import importlib
import sys
import time
from typing import Any

from .helpers.frame import get_current_frame
from .util.loop import protect_loop

_IN_TESTS = "unittest" in sys.modules


def _check_import_call_allowed(mapped_args: dict[str, Any]) -> bool:
    # If the module is already imported, we can ignore it.
    return bool((args := mapped_args.get("args")) and args[0] in sys.modules)


def _check_sleep_call_allowed(mapped_args: dict[str, Any]) -> bool:
    #
    # Avoid extracting the stack unless we need to since it
    # will have to access the linecache which can do blocking
    # I/O and we are trying to avoid blocking calls.
    #
    # frame[0] is us
    # frame[1] is check_loop
    # frame[2] is protected_loop_func
    # frame[3] is the offender
    with suppress(ValueError):
        return get_current_frame(4).f_code.co_filename.endswith("pydevd.py")
    return False


def enable() -> None:
    """Enable the detection of blocking calls in the event loop."""
    # Prevent urllib3 and requests doing I/O in event loop
    HTTPConnection.putrequest = protect_loop(  # type: ignore[method-assign]
        HTTPConnection.putrequest
    )

    # Prevent sleeping in event loop. Non-strict since 2022.02
    time.sleep = protect_loop(
        time.sleep, strict=False, check_allowed=_check_sleep_call_allowed
    )

    # Currently disabled. pytz doing I/O when getting timezone.
    # Prevent files being opened inside the event loop
    # builtins.open = protect_loop(builtins.open)

    if not _IN_TESTS:
        # unittest uses `importlib.import_module` to do mocking
        # so we cannot protect it if we are running tests
        importlib.import_module = protect_loop(
            importlib.import_module,
            strict_core=False,
            strict=False,
            check_allowed=_check_import_call_allowed,
        )
