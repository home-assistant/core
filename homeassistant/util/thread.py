"""Threading util helpers."""
import ctypes
import inspect
import sys
import threading
from typing import Any


def fix_threading_exception_logging() -> None:
    """Fix threads passing uncaught exceptions to our exception hook.

    https://bugs.python.org/issue1230540
    Fixed in Python 3.8.
    """
    if sys.version_info[:2] >= (3, 8):
        return

    run_old = threading.Thread.run

    def run(*args: Any, **kwargs: Any) -> None:
        try:
            run_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):  # pylint: disable=try-except-raise
            raise
        except Exception:  # pylint: disable=broad-except
            sys.excepthook(*sys.exc_info())

    threading.Thread.run = run  # type: ignore


def _async_raise(tid: int, exctype: Any) -> None:
    """Raise an exception in the threads with id tid."""
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")

    c_tid = ctypes.c_long(tid)
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
        _async_raise(self.ident, exctype)
