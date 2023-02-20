"""Minimal legacy asyncio.coroutine."""

# flake8: noqa
# stubbing out for integrations that have
# not yet been updated for python 3.11
# but can still run on python 3.10
#
# Remove this once rflink, fido, and blackbird
# have had their libraries updated to remove
# asyncio.coroutine
from asyncio import base_futures, constants, format_helpers
from asyncio.coroutines import _is_coroutine
import collections.abc
import functools
import inspect
import logging
import traceback
import types
import warnings

logger = logging.getLogger(__name__)


class CoroWrapper:
    # Wrapper for coroutine object in _DEBUG mode.

    def __init__(self, gen, func=None):
        assert inspect.isgenerator(gen) or inspect.iscoroutine(gen), gen
        self.gen = gen
        self.func = func  # Used to unwrap @coroutine decorator
        self._source_traceback = format_helpers.extract_stack(sys._getframe(1))
        self.__name__ = getattr(gen, "__name__", None)
        self.__qualname__ = getattr(gen, "__qualname__", None)

    def __iter__(self):
        return self

    def __next__(self):
        return self.gen.send(None)

    def send(self, value):
        return self.gen.send(value)

    def throw(self, type, value=None, traceback=None):
        return self.gen.throw(type, value, traceback)

    def close(self):
        return self.gen.close()

    @property
    def gi_frame(self):
        return self.gen.gi_frame

    @property
    def gi_running(self):
        return self.gen.gi_running

    @property
    def gi_code(self):
        return self.gen.gi_code

    def __await__(self):
        return self

    @property
    def gi_yieldfrom(self):
        return self.gen.gi_yieldfrom

    def __del__(self):
        # Be careful accessing self.gen.frame -- self.gen might not exist.
        gen = getattr(self, "gen", None)
        frame = getattr(gen, "gi_frame", None)
        if frame is not None and frame.f_lasti == -1:
            msg = f"{self!r} was never yielded from"
            tb = getattr(self, "_source_traceback", ())
            if tb:
                tb = "".join(traceback.format_list(tb))
                msg += (
                    f"\nCoroutine object created at "
                    f"(most recent call last, truncated to "
                    f"{constants.DEBUG_STACK_DEPTH} last lines):\n"
                )
                msg += tb.rstrip()
            logger.error(msg)


def legacy_coroutine(func):
    """Decorator to mark coroutines.
    If the coroutine is not yielded from before it is destroyed,
    an error message is logged.
    """
    warnings.warn(
        '"@coroutine" decorator is deprecated since Python 3.8, use "async def" instead',
        DeprecationWarning,
        stacklevel=2,
    )
    if inspect.iscoroutinefunction(func):
        # In Python 3.5 that's all we need to do for coroutines
        # defined with "async def".
        return func

    if inspect.isgeneratorfunction(func):
        coro = func
    else:

        @functools.wraps(func)
        def coro(*args, **kw):
            res = func(*args, **kw)
            if (
                base_futures.isfuture(res)
                or inspect.isgenerator(res)
                or isinstance(res, CoroWrapper)
            ):
                res = yield from res
            else:
                # If 'res' is an awaitable, run it.
                try:
                    await_meth = res.__await__
                except AttributeError:
                    pass
                else:
                    if isinstance(res, collections.abc.Awaitable):
                        res = yield from await_meth()
            return res

    wrapper = types.coroutine(coro)
    wrapper._is_coroutine = _is_coroutine  # For iscoroutinefunction().
    return wrapper
