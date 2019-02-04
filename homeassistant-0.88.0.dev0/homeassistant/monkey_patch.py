"""Monkey patch Python to work around issues causing segfaults.

Under heavy threading operations that schedule calls into
the asyncio event loop, Task objects are created. Due to
a bug in Python, GC may have an issue when switching between
the threads and objects with __del__ (which various components
in HASS have).

This monkey-patch removes the weakref.Weakset, and replaces it
with an object that ignores the only call utilizing it (the
Task.__init__ which calls _all_tasks.add(self)). It also removes
the __del__ which could trigger the future objects __del__ at
unpredictable times.

The side-effect of this manipulation of the Task is that
Task.all_tasks() is no longer accurate, and there will be no
warning emitted if a Task is GC'd while in use.

Related Python bugs:
 - https://bugs.python.org/issue26617
"""
import sys
from typing import Any


def patch_weakref_tasks() -> None:
    """Replace weakref.WeakSet to address Python 3 bug."""
    # pylint: disable=no-self-use, protected-access
    import asyncio.tasks

    class IgnoreCalls:
        """Ignore add calls."""

        def add(self, other: Any) -> None:
            """No-op add."""
            return

    asyncio.tasks.Task._all_tasks = IgnoreCalls()  # type: ignore
    try:
        del asyncio.tasks.Task.__del__
    except:  # noqa: E722 pylint: disable=bare-except
        pass


def disable_c_asyncio() -> None:
    """Disable using C implementation of asyncio.

    Required to be able to apply the weakref monkey patch.

    Requires Python 3.6+.
    """
    class AsyncioImportFinder:
        """Finder that blocks C version of asyncio being loaded."""

        PATH_TRIGGER = '_asyncio'

        def __init__(self, path_entry: str) -> None:
            if path_entry != self.PATH_TRIGGER:
                raise ImportError()

        def find_module(self, fullname: str, path: Any = None) -> None:
            """Find a module."""
            if fullname == self.PATH_TRIGGER:
                # We lint in Py35, exception is introduced in Py36
                # pylint: disable=undefined-variable
                raise ModuleNotFoundError()  # type: ignore # noqa

    sys.path_hooks.append(AsyncioImportFinder)
    sys.path.insert(0, AsyncioImportFinder.PATH_TRIGGER)

    try:
        import _asyncio  # noqa
    except ImportError:
        pass
