"""Helpers for script and automation tracing and debugging."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, TypeVar

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class LimitedSizeDict(OrderedDict[_KT, _VT]):
    """OrderedDict limited in size."""

    def __init__(self, *args: Any, **kwds: Any) -> None:
        """Initialize OrderedDict limited in size."""
        self.size_limit = kwds.pop("size_limit", None)
        super().__init__(*args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key: _KT, value: _VT) -> None:
        """Set item and check dict size."""
        super().__setitem__(key, value)
        self._check_size_limit()

    def _check_size_limit(self) -> None:
        """Check dict size and evict items in FIFO order if needed."""
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)
