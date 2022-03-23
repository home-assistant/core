"""Diagnostics for debugging.

The stream component does not have config entries itself, and all diagnostics
information is managed by dependent components (e.g. camera)
"""

from __future__ import annotations

from collections import Counter
from typing import Any


class Diagnostics:
    """Holds diagnostics counters and key/values."""

    def __init__(self) -> None:
        """Initialize Diagnostics."""
        self._counter: Counter = Counter()
        self._values: dict[str, Any] = {}

    def increment(self, key: str) -> None:
        """Increment a counter for the spcified key/event."""
        self._counter.update(Counter({key: 1}))

    def set_value(self, key: str, value: Any) -> None:
        """Update a key/value pair."""
        self._values[key] = value

    def as_dict(self) -> dict[str, Any]:
        """Return diagnostics as a debug dictionary."""
        result = {k: self._counter[k] for k in self._counter}
        result.update(self._values)
        return result
