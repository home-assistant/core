"""Run Home Assistant."""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
from typing import Any

from homeassistant import bootstrap
from homeassistant.core import callback
from homeassistant.helpers.frame import warn_use
from homeassistant.util.executor import InterruptibleThreadPoolExecutor
from homeassistant.util.thread import deadlock_safe_shutdown

# mypy: disallow-any-generics

#
# Python 3.8 has significantly less workers by default
# than Python 3.7.  In order to be consistent between
# supported versions, we need to set max_workers.
#
# In most cases the workers are not I/O bound, as they
# are sleeping/blocking waiting for data from integrations
# updating so this number should be higher than the default
# use case.
#
MAX_EXECUTOR_WORKERS = 64
TASK_CANCELATION_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class RuntimeConfig:
    """Class to hold the information for running Home Assistant."""

    config_dir: str
    skip_pip: bool = False
    safe_mode: bool = False

    verbose: bool = False

    log_rotate_days: int | None = None
    log_file: str | None = None
    log_no_color: bool = False

    debug: bool = False
    open_ui: bool = False


class HassEventLoopPolicy(asyncio.DefaultEventLoopPolicy):  # type: ignore[valid-type,misc]
    """Event loop policy for Home Assistant."""

    def __init__(self, debug: bool) -> None:
        """Init the event loop policy."""
        super().__init__()
        self.debug = debug

    @property
    def loop_name(self) -> str:
        """Return name of the loop."""
        return self._loop_factory.__name__  # type: ignore

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
        loop.set_default_executor = warn_use(  # type: ignore
            loop.set_default_executor, "sets default executor on the event loop"
        )
        return loop


@callback
def _async_loop_exception_handler(_: Any, context: dict[str, Any]) -> None:
    """Handle all exception inside the core loop."""
    kwargs = {}
    exception = context.get("exception")
    if exception:
        kwargs["exc_info"] = (type(exception), exception, exception.__traceback__)

    logging.getLogger(__package__).error(
        "Error doing job: %s", context["message"], **kwargs  # type: ignore
    )


async def setup_and_run_hass(runtime_config: RuntimeConfig) -> int:
    """Set up Home Assistant and run."""
    hass = await bootstrap.async_setup_hass(runtime_config)

    if hass is None:
        return 1

    # threading._shutdown can deadlock forever
    threading._shutdown = deadlock_safe_shutdown  # type: ignore[attr-defined] # pylint: disable=protected-access

    return await hass.async_run()


def run(runtime_config: RuntimeConfig) -> int:
    """Run Home Assistant."""
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
            # Once cpython 3.8 is no longer supported we can use the
            # the built-in loop.shutdown_default_executor
            loop.run_until_complete(_shutdown_default_executor(loop))
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


async def _shutdown_default_executor(loop: asyncio.AbstractEventLoop) -> None:
    """Backport of cpython 3.9 schedule the shutdown of the default executor."""
    future = loop.create_future()

    def _do_shutdown() -> None:
        try:
            loop._default_executor.shutdown(wait=True)  # type: ignore  # pylint: disable=protected-access
            loop.call_soon_threadsafe(future.set_result, None)
        except Exception as ex:  # pylint: disable=broad-except
            loop.call_soon_threadsafe(future.set_exception, ex)

    thread = threading.Thread(target=_do_shutdown)
    thread.start()
    try:
        await future
    finally:
        thread.join()
