"""Run Home Assistant."""
from __future__ import annotations

import asyncio
from asyncio import events
import dataclasses
import logging
import os
import subprocess
import threading
import traceback
from typing import Any

from . import bootstrap
from .core import callback
from .helpers.frame import warn_use
from .util.executor import InterruptibleThreadPoolExecutor
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
ALPINE_RELEASE_FILE = "/etc/alpine-release"

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class RuntimeConfig:
    """Class to hold the information for running Home Assistant."""

    config_dir: str
    skip_pip: bool = False
    skip_pip_packages: list[str] = dataclasses.field(default_factory=list)
    safe_mode: bool = False

    verbose: bool = False

    log_rotate_days: int | None = None
    log_file: str | None = None
    log_no_color: bool = False

    debug: bool = False
    open_ui: bool = False


def can_use_pidfd() -> bool:
    """Check if pidfd_open is available.

    Back ported from cpython 3.12
    """
    if not hasattr(os, "pidfd_open"):
        return False
    try:
        pid = os.getpid()
        os.close(os.pidfd_open(pid, 0))
    except OSError:
        # blocked by security policy like SECCOMP
        return False
    return True


class HassEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy for Home Assistant."""

    def __init__(self, debug: bool) -> None:
        """Init the event loop policy."""
        super().__init__()
        self.debug = debug
        self._watcher: asyncio.AbstractChildWatcher | None = None

    def _init_watcher(self) -> None:
        """Initialize the watcher for child processes.

        Back ported from cpython 3.12
        """
        with events._lock:  # type: ignore[attr-defined] # pylint: disable=protected-access
            if self._watcher is None:  # pragma: no branch
                if can_use_pidfd():
                    self._watcher = asyncio.PidfdChildWatcher()
                else:
                    self._watcher = asyncio.ThreadedChildWatcher()
                if threading.current_thread() is threading.main_thread():
                    self._watcher.attach_loop(
                        self._local._loop  # type: ignore[attr-defined] # pylint: disable=protected-access
                    )

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
        return loop


@callback
def _async_loop_exception_handler(_: Any, context: dict[str, Any]) -> None:
    """Handle all exception inside the core loop."""
    kwargs = {}
    if exception := context.get("exception"):
        kwargs["exc_info"] = (type(exception), exception, exception.__traceback__)

    logger = logging.getLogger(__package__)
    if source_traceback := context.get("source_traceback"):
        stack_summary = "".join(traceback.format_list(source_traceback))
        logger.error(
            "Error doing job: %s: %s",
            context["message"],
            stack_summary,
            **kwargs,  # type: ignore[arg-type]
        )
        return

    logger.error(
        "Error doing job: %s",
        context["message"],
        **kwargs,  # type: ignore[arg-type]
    )


async def setup_and_run_hass(runtime_config: RuntimeConfig) -> int:
    """Set up Home Assistant and run."""
    hass = await bootstrap.async_setup_hass(runtime_config)

    if hass is None:
        return 1

    # threading._shutdown can deadlock forever
    # pylint: disable-next=protected-access
    threading._shutdown = deadlock_safe_shutdown  # type: ignore[attr-defined]

    return await hass.async_run()


def _enable_posix_spawn() -> None:
    """Enable posix_spawn on Alpine Linux."""
    # pylint: disable=protected-access
    if subprocess._USE_POSIX_SPAWN:
        return

    # The subprocess module does not know about Alpine Linux/musl
    # and will use fork() instead of posix_spawn() which significantly
    # less efficient. This is a workaround to force posix_spawn()
    # on Alpine Linux which is supported by musl.
    subprocess._USE_POSIX_SPAWN = os.path.exists(ALPINE_RELEASE_FILE)


def run(runtime_config: RuntimeConfig) -> int:
    """Run Home Assistant."""
    _enable_posix_spawn()
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
        task.cancel()

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
