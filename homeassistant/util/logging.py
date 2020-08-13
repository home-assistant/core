"""Logging utilities."""
import asyncio
from functools import partial, wraps
import inspect
import logging
import logging.handlers
import queue
import traceback
from typing import Any, Callable, Coroutine

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant, callback


class HideSensitiveDataFilter(logging.Filter):
    """Filter API password calls."""

    def __init__(self, text: str) -> None:
        """Initialize sensitive data filter."""
        super().__init__()
        self.text = text

    def filter(self, record: logging.LogRecord) -> bool:
        """Hide sensitive data in messages."""
        record.msg = record.msg.replace(self.text, "*******")

        return True


class HomeAssistantQueueHandler(logging.handlers.QueueHandler):
    """Process the log in another thread."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        try:
            self.enqueue(record)
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)

    def handle(self, record: logging.LogRecord) -> Any:
        """
        Conditionally emit the specified logging record.

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


@callback
def async_activate_log_queue_handler(hass: HomeAssistant) -> None:
    """
    Migrate the existing log handlers to use the queue.

    This allows us to avoid blocking I/O and formatting messages
    in the event loop as log messages are written in another thread.
    """
    simple_queue = queue.SimpleQueue()  # type: ignore
    queue_handler = HomeAssistantQueueHandler(simple_queue)
    logging.root.addHandler(queue_handler)

    migrated_handlers = []
    for handler in logging.root.handlers[:]:
        if handler is queue_handler:
            continue
        logging.root.removeHandler(handler)
        migrated_handlers.append(handler)

    listener = logging.handlers.QueueListener(simple_queue, *migrated_handlers)

    listener.start()

    @callback
    def _async_stop_queue_handler(_: Any) -> None:
        """Cleanup handler."""
        logging.root.removeHandler(queue_handler)
        listener.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_stop_queue_handler)


def log_exception(format_err: Callable[..., Any], *args: Any) -> None:
    """Log an exception with additional context."""
    module = inspect.getmodule(inspect.stack()[1][0])
    if module is not None:
        module_name = module.__name__
    else:
        # If Python is unable to access the sources files, the call stack frame
        # will be missing information, so let's guard.
        # https://github.com/home-assistant/home-assistant/issues/24982
        module_name = __name__

    # Do not print the wrapper in the traceback
    frames = len(inspect.trace()) - 1
    exc_msg = traceback.format_exc(-frames)
    friendly_msg = format_err(*args)
    logging.getLogger(module_name).error("%s\n%s", friendly_msg, exc_msg)


def catch_log_exception(
    func: Callable[..., Any], format_err: Callable[..., Any], *args: Any
) -> Callable[[], None]:
    """Decorate a callback to catch and log exceptions."""

    # Check for partials to properly determine if coroutine function
    check_func = func
    while isinstance(check_func, partial):
        check_func = check_func.func

    wrapper_func = None
    if asyncio.iscoroutinefunction(check_func):

        @wraps(func)
        async def async_wrapper(*args: Any) -> None:
            """Catch and log exception."""
            try:
                await func(*args)
            except Exception:  # pylint: disable=broad-except
                log_exception(format_err, *args)

        wrapper_func = async_wrapper
    else:

        @wraps(func)
        def wrapper(*args: Any) -> None:
            """Catch and log exception."""
            try:
                func(*args)
            except Exception:  # pylint: disable=broad-except
                log_exception(format_err, *args)

        wrapper_func = wrapper
    return wrapper_func


def catch_log_coro_exception(
    target: Coroutine[Any, Any, Any], format_err: Callable[..., Any], *args: Any
) -> Coroutine[Any, Any, Any]:
    """Decorate a coroutine to catch and log exceptions."""

    async def coro_wrapper(*args: Any) -> Any:
        """Catch and log exception."""
        try:
            return await target
        except Exception:  # pylint: disable=broad-except
            log_exception(format_err, *args)
            return None

    return coro_wrapper()


def async_create_catching_coro(target: Coroutine) -> Coroutine:
    """Wrap a coroutine to catch and log exceptions.

    The exception will be logged together with a stacktrace of where the
    coroutine was wrapped.

    target: target coroutine.
    """
    trace = traceback.extract_stack()
    wrapped_target = catch_log_coro_exception(
        target,
        lambda *args: "Exception in {} called from\n {}".format(
            target.__name__,  # type: ignore
            "".join(traceback.format_list(trace[:-1])),
        ),
    )

    return wrapped_target
