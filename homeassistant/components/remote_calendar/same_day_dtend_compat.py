"""Compatibility layer for same-day DTEND all-day events.

Some calendar providers use DTSTART and DTEND with the same date for all-day events.
RFC 5545 specifies DTEND should be the next day (non-inclusive).
"""

from collections.abc import Generator
import contextlib
import contextvars


_same_day_dtend_compat = contextvars.ContextVar("same_day_dtend_compat", default=False)


@contextlib.contextmanager
def enable_same_day_dtend_compat() -> Generator[None]:
    """Context manager to enable same-day DTEND compatibility mode."""
    token = _same_day_dtend_compat.set(True)
    try:
        yield
    finally:
        _same_day_dtend_compat.reset(token)


def is_same_day_dtend_compat_enabled() -> bool:
    """Check if same-day DTEND compatibility mode is enabled."""
    return _same_day_dtend_compat.get()
