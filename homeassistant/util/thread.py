"""Threading util helpers."""
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
