"""Threading util helpers."""
import ctypes
import inspect
import logging
import threading
from typing import Any

SHUTDOWN_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


def deadlock_safe_shutdown() -> None:
    """Shutdown that will not deadlock."""
    # threading._shutdown can deadlock forever
    # see https://github.com/justengel/continuous_threading#shutdown-update
    # for additional detail
    for thread in threading.enumerate():
        try:
            if (
                thread is not threading.main_thread()
                and thread.is_alive()
                and not thread.daemon
            ):
                thread.join(SHUTDOWN_TIMEOUT)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Failed to join thread: %s", err)


def async_raise(tid: int, exctype: Any) -> None:
    """Raise an exception in the threads with id tid."""
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")

    c_tid = ctypes.c_ulong(tid)  # changed in python 3.7+
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(c_tid, ctypes.py_object(exctype))

    if res == 1:
        return

    # "if it returns a number greater than one, you're in trouble,
    # and you should call it again with exc=NULL to revert the effect"
    ctypes.pythonapi.PyThreadState_SetAsyncExc(c_tid, None)
    raise SystemError("PyThreadState_SetAsyncExc failed")


class ThreadWithException(threading.Thread):
    """A thread class that supports raising exception in the thread from another thread.

    Based on
    https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread/49877671

    """

    def raise_exc(self, exctype: Any) -> None:
        """Raise the given exception type in the context of this thread."""
        assert self.ident
        async_raise(self.ident, exctype)
