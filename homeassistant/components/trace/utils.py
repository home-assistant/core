"""Helpers for script and automation tracing and debugging."""
from collections import OrderedDict
from datetime import timedelta
from typing import Any

from homeassistant.helpers.json import JSONEncoder as HAJSONEncoder


class LimitedSizeDict(OrderedDict):
    """OrderedDict limited in size."""

    def __init__(self, *args, **kwds):
        """Initialize OrderedDict limited in size."""
        self.size_limit = kwds.pop("size_limit", None)
        OrderedDict.__init__(self, *args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key, value):
        """Set item and check dict size."""
        OrderedDict.__setitem__(self, key, value)
        self._check_size_limit()

    def _check_size_limit(self):
        """Check dict size and evict items in FIFO order if needed."""
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)


class TraceJSONEncoder(HAJSONEncoder):
    """JSONEncoder that supports Home Assistant objects and falls back to repr(o)."""

    def default(self, o: Any) -> Any:
        """Convert certain objects.

        Fall back to repr(o).
        """
        if isinstance(o, timedelta):
            return {"__type": str(type(o)), "total_seconds": o.total_seconds()}
        try:
            return super().default(o)
        except TypeError:
            return {"__type": str(type(o)), "repr": repr(o)}
