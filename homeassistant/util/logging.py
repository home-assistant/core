"""Logging utilities."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Coroutine
from functools import partial, wraps
import inspect
import logging
import logging.handlers
from queue import SimpleQueue
import time
import traceback
from typing import Any, cast, overload, override

from homeassistant.core import (
    HassJobType,
    HomeAssistant,
    callback,
    get_hassjob_callable_job_type,
)

_LOGGER = logging.getLogger(__name__)


class HomeAssistantQueueListener(logging.handlers.QueueListener):
    """Custom QueueListener to watch for noisy loggers."""

    LOG_COUNTS_RESET_INTERVAL = 300
    MAX_LOGS_COUNT = 200

    EXCLUDED_LOG_COUNT_MODULES = [
        "homeassistant.components.automation",
        "homeassistant.components.script",
        "homeassistant.setup",
        "homeassistant.util.logging",
    ]

    _last_reset: float
    _log_counts: dict[str, int]

    def __init__(
        self, queue: SimpleQueue[logging.Handler], *handlers: logging.Handler
    ) -> None:
        """Initialize the handler."""
        super().__init__(queue, *handlers)
        self._module_log_count_skip_flags: dict[str, bool] = {}
        self._reset_counters(time.time())

    @override
    def handle(self, record: logging.LogRecord) -> None:
        """Handle the record."""
        super().handle(record)

        if record.levelno < logging.INFO:
            return

        if (record.created - self._last_reset) > self.LOG_COUNTS_RESET_INTERVAL:
            self._reset_counters(record.created)

        module_name = record.name

        if skip_flag := self._module_log_count_skip_flags.get(module_name):
            return

        if skip_flag is None and self._update_skip_flags(module_name):
            return

        self._log_counts[module_name] += 1
        module_count = self._log_counts[module_name]
        if module_count < self.MAX_LOGS_COUNT:
            return

        _LOGGER.warning(
            "Module %s is logging too frequently. %d messages since last count",
            module_name,
            module_count,
        )
        self._module_log_count_skip_flags[module_name] = True

    def _reset_counters(self, time_sec: float) -> None:
        _LOGGER.debug("Resetting log counters")
        self._last_reset = time_sec
        self._log_counts = defaultdict(int)

    def _update_skip_flags(self, module_name: str) -> bool:
        excluded = any(
            module_name.startswith(prefix) for prefix in self.EXCLUDED_LOG_COUNT_MODULES
        )
        self._module_log_count_skip_flags[module_name] = excluded
        return excluded


class HomeAssistantQueueHandler(logging.handlers.QueueHandler):
    """Process the log in another thread."""

    listener: logging.handlers.QueueListener | None = None

    def handle(self, record: logging.LogRecord) -> Any:
        """Conditionally emit the specified logging record.

        Depending on which filters have been added to the handler, push the new
        records onto the backing Queue.

        The default python logger Handler acquires a lock
        in the parent class which we do not need as
        SimpleQueue is already thread safe.

        See https://bugs.python.org/issue24645
        """
        return_value = self.filter(record)
        if return_value:
            self.emit(record)
        return return_value

    def close(self) -> None:
        """Tidy up any resources used by the handler.

        This adds shutdown of the QueueListener
        """
        super().close()
        if not self.listener:
            return
        self.listener.stop()
        self.listener = None


@callback
def async_activate_log_queue_handler(hass: HomeAssistant) -> None:
    """Migrate the existing log handlers to use the queue.

    This allows us to avoid blocking I/O and formatting messages
    in the event loop as log messages are written in another thread.
    """
    simple_queue: SimpleQueue[logging.Handler] = SimpleQueue()
    queue_handler = HomeAssistantQueueHandler(simple_queue)
    logging.root.addHandler(queue_handler)

    migrated_handlers: list[logging.Handler] = []
    for handler in logging.root.handlers[:]:
        if handler is queue_handler:
            continue
        logging.root.removeHandler(handler)
        migrated_handlers.append(handler)

    listener = HomeAssistantQueueListener(simple_queue, *migrated_handlers)
    queue_handler.listener = listener

    listener.start()


def log_exception[*_Ts](format_err: Callable[[*_Ts], Any], *args: *_Ts) -> None:
    """Log an exception with additional context."""
    module = inspect.getmodule(inspect.stack(context=0)[1].frame)
    if module is not None:
        module_name = module.__name__
    else:
        # If Python is unable to access the sources files, the call stack frame
        # will be missing information, so let's guard.
        # https://github.com/home-assistant/core/issues/24982
        module_name = __name__

    # Do not print the wrapper in the traceback
    frames = len(inspect.trace()) - 1
    exc_msg = traceback.format_exc(-frames)
    friendly_msg = format_err(*args)
    logging.getLogger(module_name).error("%s\n%s", friendly_msg, exc_msg)


async def _async_wrapper[*_Ts](
    async_func: Callable[[*_Ts], Coroutine[Any, Any, None]],
    format_err: Callable[[*_Ts], Any],
    *args: *_Ts,
) -> None:
    """Catch and log exception."""
    try:
        await async_func(*args)
    except Exception:  # noqa: BLE001
        log_exception(format_err, *args)


def _sync_wrapper[*_Ts](
    func: Callable[[*_Ts], Any], format_err: Callable[[*_Ts], Any], *args: *_Ts
) -> None:
    """Catch and log exception."""
    try:
        func(*args)
    except Exception:  # noqa: BLE001
        log_exception(format_err, *args)


@callback
def _callback_wrapper[*_Ts](
    func: Callable[[*_Ts], Any], format_err: Callable[[*_Ts], Any], *args: *_Ts
) -> None:
    """Catch and log exception."""
    try:
        func(*args)
    except Exception:  # noqa: BLE001
        log_exception(format_err, *args)


@overload
def catch_log_exception[*_Ts](
    func: Callable[[*_Ts], Coroutine[Any, Any, Any]],
    format_err: Callable[[*_Ts], Any],
    job_type: HassJobType | None = None,
) -> Callable[[*_Ts], Coroutine[Any, Any, None]]: ...


@overload
def catch_log_exception[*_Ts](
    func: Callable[[*_Ts], Any],
    format_err: Callable[[*_Ts], Any],
    job_type: HassJobType | None = None,
) -> Callable[[*_Ts], None] | Callable[[*_Ts], Coroutine[Any, Any, None]]: ...


def catch_log_exception[*_Ts](
    func: Callable[[*_Ts], Any],
    format_err: Callable[[*_Ts], Any],
    job_type: HassJobType | None = None,
) -> Callable[[*_Ts], None] | Callable[[*_Ts], Coroutine[Any, Any, None]]:
    """Decorate a function func to catch and log exceptions.

    If func is a coroutine function, a coroutine function will be returned.
    If func is a callback, a callback will be returned.
    """
    if job_type is None:
        job_type = get_hassjob_callable_job_type(func)

    if job_type is HassJobType.Coroutinefunction:
        async_func = cast(Callable[[*_Ts], Coroutine[Any, Any, None]], func)
        return wraps(async_func)(partial(_async_wrapper, async_func, format_err))  # type: ignore[return-value]

    if job_type is HassJobType.Callback:
        return wraps(func)(partial(_callback_wrapper, func, format_err))  # type: ignore[return-value]

    return wraps(func)(partial(_sync_wrapper, func, format_err))  # type: ignore[return-value]


def catch_log_coro_exception[_T, *_Ts](
    target: Coroutine[Any, Any, _T], format_err: Callable[[*_Ts], Any], *args: *_Ts
) -> Coroutine[Any, Any, _T | None]:
    """Decorate a coroutine to catch and log exceptions."""

    async def coro_wrapper(*args: *_Ts) -> _T | None:
        """Catch and log exception."""
        try:
            return await target
        except Exception:  # noqa: BLE001
            log_exception(format_err, *args)
            return None

    return coro_wrapper(*args)


def async_create_catching_coro[_T](
    target: Coroutine[Any, Any, _T],
) -> Coroutine[Any, Any, _T | None]:
    """Wrap a coroutine to catch and log exceptions.

    The exception will be logged together with a stacktrace of where the
    coroutine was wrapped.

    target: target coroutine.
    """
    trace = traceback.extract_stack()
    return catch_log_coro_exception(
        target,
        lambda: (
            f"Exception in {target.__name__} called from\n"
            + "".join(traceback.format_list(trace[:-1]))
        ),
    )
