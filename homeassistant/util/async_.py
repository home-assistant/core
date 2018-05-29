"""Asyncio backports for Python 3.4.3 compatibility."""
import concurrent.futures
import threading
import logging
from asyncio import coroutines
from asyncio.futures import Future

from asyncio import ensure_future


_LOGGER = logging.getLogger(__name__)


def _set_result_unless_cancelled(fut, result):
    """Set the result only if the Future was not cancelled."""
    if fut.cancelled():
        return
    fut.set_result(result)


def _set_concurrent_future_state(concurr, source):
    """Copy state from a future to a concurrent.futures.Future."""
    assert source.done()
    if source.cancelled():
        concurr.cancel()
    if not concurr.set_running_or_notify_cancel():
        return
    exception = source.exception()
    if exception is not None:
        concurr.set_exception(exception)
    else:
        result = source.result()
        concurr.set_result(result)


def _copy_future_state(source, dest):
    """Copy state from another Future.

    The other Future may be a concurrent.futures.Future.
    """
    assert source.done()
    if dest.cancelled():
        return
    assert not dest.done()
    if source.cancelled():
        dest.cancel()
    else:
        exception = source.exception()
        if exception is not None:
            dest.set_exception(exception)
        else:
            result = source.result()
            dest.set_result(result)


def _chain_future(source, destination):
    """Chain two futures so that when one completes, so does the other.

    The result (or exception) of source will be copied to destination.
    If destination is cancelled, source gets cancelled too.
    Compatible with both asyncio.Future and concurrent.futures.Future.
    """
    if not isinstance(source, (Future, concurrent.futures.Future)):
        raise TypeError('A future is required for source argument')
    if not isinstance(destination, (Future, concurrent.futures.Future)):
        raise TypeError('A future is required for destination argument')
    # pylint: disable=protected-access
    source_loop = source._loop if isinstance(source, Future) else None
    dest_loop = destination._loop if isinstance(destination, Future) else None

    def _set_state(future, other):
        if isinstance(future, Future):
            _copy_future_state(other, future)
        else:
            _set_concurrent_future_state(future, other)

    def _call_check_cancel(destination):
        if destination.cancelled():
            if source_loop is None or source_loop is dest_loop:
                source.cancel()
            else:
                source_loop.call_soon_threadsafe(source.cancel)

    def _call_set_state(source):
        if dest_loop is None or dest_loop is source_loop:
            _set_state(destination, source)
        else:
            dest_loop.call_soon_threadsafe(_set_state, destination, source)

    destination.add_done_callback(_call_check_cancel)
    source.add_done_callback(_call_set_state)


def run_coroutine_threadsafe(coro, loop):
    """Submit a coroutine object to a given event loop.

    Return a concurrent.futures.Future to access the result.
    """
    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError('Cannot be called from within the event loop')

    if not coroutines.iscoroutine(coro):
        raise TypeError('A coroutine object is required')
    future = concurrent.futures.Future()

    def callback():
        """Handle the call to the coroutine."""
        try:
            # pylint: disable=deprecated-method
            _chain_future(ensure_future(coro, loop=loop), future)
        # pylint: disable=broad-except
        except Exception as exc:
            if future.set_running_or_notify_cancel():
                future.set_exception(exc)
            else:
                _LOGGER.warning("Exception on lost future: ", exc_info=True)

    loop.call_soon_threadsafe(callback)
    return future


def fire_coroutine_threadsafe(coro, loop):
    """Submit a coroutine object to a given event loop.

    This method does not provide a way to retrieve the result and
    is intended for fire-and-forget use. This reduces the
    work involved to fire the function on the loop.
    """
    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError('Cannot be called from within the event loop')

    if not coroutines.iscoroutine(coro):
        raise TypeError('A coroutine object is required: %s' % coro)

    def callback():
        """Handle the firing of a coroutine."""
        # pylint: disable=deprecated-method
        ensure_future(coro, loop=loop)

    loop.call_soon_threadsafe(callback)
    return


def run_callback_threadsafe(loop, callback, *args):
    """Submit a callback object to a given event loop.

    Return a concurrent.futures.Future to access the result.
    """
    ident = loop.__dict__.get("_thread_ident")
    if ident is not None and ident == threading.get_ident():
        raise RuntimeError('Cannot be called from within the event loop')

    future = concurrent.futures.Future()

    def run_callback():
        """Run callback and store result."""
        try:
            future.set_result(callback(*args))
        # pylint: disable=broad-except
        except Exception as exc:
            if future.set_running_or_notify_cancel():
                future.set_exception(exc)
            else:
                _LOGGER.warning("Exception on lost future: ", exc_info=True)

    loop.call_soon_threadsafe(run_callback)
    return future
