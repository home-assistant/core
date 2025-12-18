"""Run Home Assistant."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
import dataclasses
from datetime import datetime
import errno
import fcntl
from io import TextIOWrapper
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from time import monotonic
import traceback
from typing import Any

import packaging.tags

from . import bootstrap
from .const import __version__
from .core import callback
from .helpers.frame import warn_use
from .util.executor import InterruptibleThreadPoolExecutor
from .util.resource import set_open_file_descriptor_limit
from .util.thread import deadlock_safe_shutdown

#
# Some Python versions may have different number of workers by default
# than others.  In order to be consistent between
# supported versions, we need to set max_workers.
#
# In most cases the workers are not I/O bound, as they
# are sleeping/blocking waiting for data from integrations
# updating so this number should be higher than the default
# use case.
#
MAX_EXECUTOR_WORKERS = 64
TASK_CANCELATION_TIMEOUT = 5

# Lock file configuration
LOCK_FILE_NAME = ".ha_run.lock"
LOCK_FILE_VERSION = 1  # Increment if format changes

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class SingleExecutionLock:
    """Context object for single execution lock."""

    exit_code: int | None = None


def _write_lock_info(lock_file: TextIOWrapper) -> None:
    """Write current instance information to the lock file.

    Args:
        lock_file: The open lock file handle.
    """
    lock_file.seek(0)
    lock_file.truncate()

    instance_info = {
        "pid": os.getpid(),
        "version": LOCK_FILE_VERSION,
        "ha_version": __version__,
        "start_ts": time.time(),
    }
    json.dump(instance_info, lock_file)
    lock_file.flush()


def _report_existing_instance(lock_file_path: Path, config_dir: str) -> None:
    """Report that another instance is already running.

    Attempts to read the lock file to provide details about the running instance.
    """
    error_msg: list[str] = []
    error_msg.append("Error: Another Home Assistant instance is already running!")

    # Try to read information about the existing instance
    try:
        with open(lock_file_path, encoding="utf-8") as f:
            if content := f.read().strip():
                existing_info = json.loads(content)
                start_dt = datetime.fromtimestamp(existing_info["start_ts"])
                # Format with timezone abbreviation if available, otherwise add local time indicator
                if tz_abbr := start_dt.strftime("%Z"):
                    start_time = start_dt.strftime(f"%Y-%m-%d %H:%M:%S {tz_abbr}")
                else:
                    start_time = (
                        start_dt.strftime("%Y-%m-%d %H:%M:%S") + " (local time)"
                    )

                error_msg.append(f"  PID: {existing_info['pid']}")
                error_msg.append(f"  Version: {existing_info['ha_version']}")
                error_msg.append(f"  Started: {start_time}")
            else:
                error_msg.append("  Unable to read lock file details.")
    except (json.JSONDecodeError, OSError) as ex:
        error_msg.append(f"  Unable to read lock file details: {ex}")

    error_msg.append(f"  Config directory: {config_dir}")
    error_msg.append("")
    error_msg.append("Please stop the existing instance before starting a new one.")

    for line in error_msg:
        print(line, file=sys.stderr)  # noqa: T201


@contextmanager
def ensure_single_execution(config_dir: str) -> Generator[SingleExecutionLock]:
    """Ensure only one Home Assistant instance runs per config directory.

    Uses file locking to prevent multiple instances from running with the
    same configuration directory, which can cause data corruption.

    Returns a context object with exit_code attribute that will be set
    if another instance is already running.
    """
    lock_file_path = Path(config_dir) / LOCK_FILE_NAME
    lock_context = SingleExecutionLock()

    # Open with 'a+' mode to avoid truncating existing content
    # This allows us to read existing content if lock fails
    with open(lock_file_path, "a+", encoding="utf-8") as lock_file:
        # Try to acquire an exclusive, non-blocking lock
        # This will raise BlockingIOError if lock is already held
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another instance is already running
            _report_existing_instance(lock_file_path, config_dir)
            lock_context.exit_code = 1
            yield lock_context
            return  # Exit early since we couldn't get the lock

        # If we got the lock (no exception), write our instance info
        _write_lock_info(lock_file)

        # Yield the context - lock will be released when the with statement closes the file
        # IMPORTANT: We don't unlink the file to avoid races where multiple processes
        # could create different lock files
        yield lock_context


@dataclasses.dataclass(slots=True)
class RuntimeConfig:
    """Class to hold the information for running Home Assistant."""

    config_dir: str
    skip_pip: bool = False
    skip_pip_packages: list[str] = dataclasses.field(default_factory=list)
    recovery_mode: bool = False

    verbose: bool = False

    log_rotate_days: int | None = None
    log_file: str | None = None
    log_no_color: bool = False

    debug: bool = False
    open_ui: bool = False

    safe_mode: bool = False


class HassEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy for Home Assistant."""

    def __init__(self, debug: bool) -> None:
        """Init the event loop policy."""
        super().__init__()
        self.debug = debug

    @property
    def loop_name(self) -> str:
        """Return name of the loop."""
        return self._loop_factory.__name__  # type: ignore[no-any-return,attr-defined]

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop."""
        loop: asyncio.AbstractEventLoop = super().new_event_loop()
        loop.set_exception_handler(_async_loop_exception_handler)
        if self.debug:
            loop.set_debug(True)

        executor = InterruptibleThreadPoolExecutor(
            thread_name_prefix="SyncWorker", max_workers=MAX_EXECUTOR_WORKERS
        )
        loop.set_default_executor(executor)
        loop.set_default_executor = warn_use(  # type: ignore[method-assign]
            loop.set_default_executor, "sets default executor on the event loop"
        )
        # bind the built-in time.monotonic directly as loop.time to avoid the
        # overhead of the additional method call since its the most called loop
        # method and its roughly 10%+ of all the call time in base_events.py
        loop.time = monotonic  # type: ignore[method-assign]
        return loop


@callback
def _async_loop_exception_handler(
    loop: asyncio.AbstractEventLoop,
    context: dict[str, Any],
) -> None:
    """Handle all exception inside the core loop."""
    fatal_error: str | None = None
    kwargs = {}
    if exception := context.get("exception"):
        kwargs["exc_info"] = (type(exception), exception, exception.__traceback__)
        if isinstance(exception, OSError) and exception.errno == errno.EMFILE:
            # Too many open files – something is leaking them, and it's likely
            # to be quite unrecoverable if the event loop can't pump messages
            # (e.g. unable to accept a socket).
            fatal_error = str(exception)

    logger = logging.getLogger(__package__)
    if source_traceback := context.get("source_traceback"):
        stack_summary = "".join(traceback.format_list(source_traceback))
        logger.error(
            "Error doing job: %s (task: %s): %s",
            context["message"],
            context.get("task"),
            stack_summary,
            **kwargs,  # type: ignore[arg-type]
        )
        return

    logger.error(
        "Error doing job: %s (task: %s)",
        context["message"],
        context.get("task"),
        **kwargs,  # type: ignore[arg-type]
    )

    if fatal_error:
        logger.error(
            "Fatal error '%s' raised in event loop, shutting it down",
            fatal_error,
        )
        loop.stop()
        loop.close()


async def setup_and_run_hass(runtime_config: RuntimeConfig) -> int:
    """Set up Home Assistant and run."""
    hass = await bootstrap.async_setup_hass(runtime_config)

    if hass is None:
        return 1

    # threading._shutdown can deadlock forever
    threading._shutdown = deadlock_safe_shutdown  # type: ignore[attr-defined]  # noqa: SLF001

    return await hass.async_run()


def _enable_posix_spawn() -> None:
    """Enable posix_spawn on Alpine Linux."""
    if subprocess._USE_POSIX_SPAWN:  # noqa: SLF001
        return

    # The subprocess module does not know about Alpine Linux/musl
    # and will use fork() instead of posix_spawn() which significantly
    # less efficient. This is a workaround to force posix_spawn()
    # when using musl since cpython is not aware its supported.
    tag = next(packaging.tags.sys_tags())
    subprocess._USE_POSIX_SPAWN = "musllinux" in tag.platform  # type: ignore[misc]  # noqa: SLF001


def run(runtime_config: RuntimeConfig) -> int:
    """Run Home Assistant."""
    _enable_posix_spawn()
    set_open_file_descriptor_limit()
    asyncio.set_event_loop_policy(HassEventLoopPolicy(runtime_config.debug))
    # Backport of cpython 3.9 asyncio.run with a _cancel_all_tasks that times out
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(setup_and_run_hass(runtime_config))
    finally:
        try:
            _cancel_all_tasks_with_timeout(loop, TASK_CANCELATION_TIMEOUT)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def _cancel_all_tasks_with_timeout(
    loop: asyncio.AbstractEventLoop, timeout: int
) -> None:
    """Adapted _cancel_all_tasks from python 3.9 with a timeout."""
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel("Final process shutdown")

    loop.run_until_complete(asyncio.wait(to_cancel, timeout=timeout))

    for task in to_cancel:
        if task.cancelled():
            continue
        if not task.done():
            _LOGGER.warning(
                "Task could not be canceled and was still running after shutdown: %s",
                task,
            )
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )
