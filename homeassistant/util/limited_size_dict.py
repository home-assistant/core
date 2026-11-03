"""Helpers for script and automation tracing and debugging."""

from collections import OrderedDict
from typing import Any, Self, override


class LimitedSizeDict[_KT, _VT](OrderedDict[_KT, _VT]):
    """OrderedDict limited in size."""

    def __init__(self, *args: Any, **kwds: Any) -> None:
        """Initialize OrderedDict limited in size."""
        self.size_limit = kwds.pop("size_limit", None)
        super().__init__(*args, **kwds)
        self._check_size_limit()

    @override
    def __setitem__(self, key: _KT, value: _VT) -> None:
        """Set item and check dict size."""
        super().__setitem__(key, value)
        self._check_size_limit()

    @override
    def copy(self) -> Self:
        """Return a shallow copy with the same size limit."""
        return self.__class__(self, size_limit=self.size_limit)

    @override
    def __or__(self, other: Any) -> Any:
        """Return the union with the same size limit."""
        if not isinstance(other, dict):
            return NotImplemented
        return self.__class__(super().__or__(other), size_limit=self.size_limit)

    @override
    def __ror__(self, other: Any) -> Any:
        """Return the reflected union with the same size limit."""
        if not isinstance(other, dict):
            return NotImplemented
        return self.__class__(super().__ror__(other), size_limit=self.size_limit)

    def _check_size_limit(self) -> None:
        """Check dict size and evict items in FIFO order if needed."""
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)
