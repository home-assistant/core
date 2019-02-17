"""Logging utilities."""
import asyncio
from asyncio.events import AbstractEventLoop
from functools import partial, wraps, update_wrapper
import inspect
import logging
import threading
import traceback
import time
from types import (MethodType, FunctionType, GeneratorType)
from typing import Any, Callable, Optional, Union

from .async_ import run_coroutine_threadsafe


class HideSensitiveDataFilter(logging.Filter):
    """Filter API password calls."""

    def __init__(self, text: str) -> None:
        """Initialize sensitive data filter."""
        super().__init__()
        self.text = text

    def filter(self, record: logging.LogRecord) -> bool:
        """Hide sensitive data in messages."""
        record.msg = record.msg.replace(self.text, '*******')

        return True


# pylint: disable=invalid-name
class AsyncHandler:
    """Logging handler wrapper to add an async layer."""

    def __init__(
            self, loop: AbstractEventLoop, handler: logging.Handler) -> None:
        """Initialize async logging handler wrapper."""
        self.handler = handler
        self.loop = loop
        self._queue = asyncio.Queue(loop=loop)  # type: asyncio.Queue
        self._thread = threading.Thread(target=self._process)

        # Delegate from handler
        self.setLevel = handler.setLevel
        self.setFormatter = handler.setFormatter
        self.addFilter = handler.addFilter
        self.removeFilter = handler.removeFilter
        self.filter = handler.filter
        self.flush = handler.flush
        self.handle = handler.handle
        self.handleError = handler.handleError
        self.format = handler.format

        self._thread.start()

    def close(self) -> None:
        """Wrap close to handler."""
        self.emit(None)

    async def async_close(self, blocking: bool = False) -> None:
        """Close the handler.

        When blocking=True, will wait till closed.
        """
        await self._queue.put(None)

        if blocking:
            while self._thread.is_alive():
                await asyncio.sleep(0, loop=self.loop)

    def emit(self, record: Optional[logging.LogRecord]) -> None:
        """Process a record."""
        ident = self.loop.__dict__.get("_thread_ident")

        # inside eventloop
        if ident is not None and ident == threading.get_ident():
            self._queue.put_nowait(record)
        # from a thread/executor
        else:
            self.loop.call_soon_threadsafe(self._queue.put_nowait, record)

    def __repr__(self) -> str:
        """Return the string names."""
        return str(self.handler)

    def _process(self) -> None:
        """Process log in a thread."""
        while True:
            record = run_coroutine_threadsafe(
                self._queue.get(), self.loop).result()

            if record is None:
                self.handler.close()
                return

            self.handler.emit(record)

    def createLock(self) -> None:
        """Ignore lock stuff."""
        pass

    def acquire(self) -> None:
        """Ignore lock stuff."""
        pass

    def release(self) -> None:
        """Ignore lock stuff."""
        pass

    @property
    def level(self) -> int:
        """Wrap property level to handler."""
        return self.handler.level

    @property
    def formatter(self) -> Optional[logging.Formatter]:
        """Wrap property formatter to handler."""
        return self.handler.formatter

    @property
    def name(self) -> str:
        """Wrap property set_name to handler."""
        return self.handler.get_name()  # type: ignore

    @name.setter
    def name(self, name: str) -> None:
        """Wrap property get_name to handler."""
        self.handler.set_name(name)  # type: ignore


def catch_log_exception(
        func: Callable[..., Any],
        format_err: Callable[..., Any],
        *args: Any) -> Callable[[], None]:
    """Decorate an callback to catch and log exceptions."""
    def log_exception(*args: Any) -> None:
        module_name = inspect.getmodule(inspect.trace()[1][0]).__name__
        # Do not print the wrapper in the traceback
        frames = len(inspect.trace()) - 1
        exc_msg = traceback.format_exc(-frames)
        friendly_msg = format_err(*args)
        logging.getLogger(module_name).error('%s\n%s', friendly_msg, exc_msg)

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
                log_exception(*args)
        wrapper_func = async_wrapper
    else:
        @wraps(func)
        def wrapper(*args: Any) -> None:
            """Catch and log exception."""
            try:
                func(*args)
            except Exception:  # pylint: disable=broad-except
                log_exception(*args)
        wrapper_func = wrapper
    return wrapper_func


def log_it(
    func: Union[MethodType, FunctionType, GeneratorType],
) -> Union[MethodType, FunctionType, GeneratorType]:
    """
    Logs the function call.

    :param func: callable object.
    :type func: Union[MethodType, FunctionType, GeneratorType]
    :return: either the callable object or a wrapper.
    :rtype: Union[MethodType, FunctionType, GeneratorType]
    """

    if func.__code__.co_flags & 0x20:
        return func

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(func.__module__)

        func_name, arg_string = _func_arg_string(func, args, kwargs)
        logger.debug(func_name + arg_string)
        return func(*args, **kwargs)

    return update_wrapper(wrapper, func)


def log_it_with_return(
    func: Union[MethodType, FunctionType, GeneratorType],
) -> Union[MethodType, FunctionType, GeneratorType]:
    """
    Logs the function call and return data.

    :param func: callable object
    :type func: Union[MethodType, FunctionType, GeneratorType]
    :return: either the callable object or a wrapper
    :rtype: Union[MethodType, FunctionType, GeneratorType]
    """

    if func.__code__.co_flags & 0x20:
        return func

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(func.__module__)

        func_name, arg_string = _func_arg_string(func, args, kwargs)
        logger.debug(func_name + arg_string)

        result = func(*args, **kwargs)
        logger.debug('{0} => {1}'.format(func_name, repr(result)))

        return result


    return update_wrapper(wrapper, func)


def log_it_with_timer(
    func: Union[MethodType, FunctionType, GeneratorType],
) -> Union[MethodType, FunctionType, GeneratorType]:
    """
    Logs the function call and return data with timing the call.

    :param func: callable object
    :type func: Union[MethodType, FunctionType, GeneratorType]
    :return: either the callable object or a wrapper
    :rtype: Union[MethodType, FunctionType, GeneratorType]
    """

    if func.__code__.co_flags & 0x20:
        return func

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(func.__module__)

        func_name, arg_string = _func_arg_string(func, args, kwargs)
        logger.debug(func_name + arg_string)

        start = time.time()
        result = func(*args, **kwargs)
        stop = time.time()

        resolutions = (
            (1, 'sec'),
            (1000, 'ms'),
            (1000000, 'μs'),
            (1000000000, 'ns'),
        )

        for divider, suffix in resolutions:
            duration = int(round((stop - start) / divider))
            if duration > 0:
                break
        else:
            duration = 'unknown'
            suffix = ''

        logger.debug(
            'duration: {0} {1} - {2} => {3}'.format(
                duration,
                suffix,
                func_name,
                repr(result)
            )
        )

    return update_wrapper(wrapper, func)


def _func_arg_string(
    func: Union[MethodType, FunctionType],
    args: tuple,
    kwargs: dict
) -> (str, str):
    """
    Creates a string representation of a function/method call with
    supplied/default positional and keyword arguments.
    example:
        module_name.ClassName.method_name(
            arg_name=arg_value,
            keyword_name=keyword_value
        )
        module_name.function_name(
            arg_name=arg_value,
            keyword_name=keyword_value
        )

    :param func: wrapped function or method.
    :type func: Union[MethodType, FunctionType]
    :param args: tuple of positional arguments.
    :type args: tuple
    :param kwargs: dict of keyword arguments.
    :type kwargs: dict
    :return: string representation of the function and supplied arguments
    :rtype: tuple(str, str)
    """

    class_name = ""
    arg_names = inspect.getfullargspec(func)[0]
    start = 0
    if arg_names:
        if arg_names[0] == "self":
            class_name = args[0].__class__.__name__ + "."
            start = 1

    res = []
    append = res.append

    stack = inspect.stack()

    func_path = []

    # iterate over the stack to check for functions being
    # nested inside of functions or methods.
    for item in stack:
        # this is where we want to stop so we do not include any of the
        # internal path information.
        if item.function == '_WorkItem':
            func_path = func_path[1:]
            break
        if item.function == '_func_arg_string':
            break
        if item.function == 'wrapper':
            continue
        # this is where the check gets done to see if a function
        # is nested inside of a method. and if it is this is
        # where we obtain the class name
        if 'self' in item.frame.f_locals:
            func_path.insert(0, item.frame.f_locals['self'].__class__.__name__)

        func_path.insert(0, item.function)

    func_path += [func.__name__]

    for key, value in list(zip(arg_names, args))[start:]:
        append(str(key) + "=" + repr(value))

    for key, value in kwargs.items():
        append(str(key) + "=" + repr(value))

    f_name = class_name + '.'.join(func_path)

    return f_name, "(" + ", ".join(res) + ")"
