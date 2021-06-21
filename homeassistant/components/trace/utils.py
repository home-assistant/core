"""Helpers for script and automation tracing and debugging."""
from collections import OrderedDict


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
