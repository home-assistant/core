"""Read cache wrapper for the Modbus Hub methods."""
from functools import lru_cache, partial
import time

CACHED_METHODS = ["read_input_registers", "read_holding_registers"]


@lru_cache(maxsize=32)
def _read_cached(hub, method, ttl_bucket, *args, **kvargs):
    """Return cached or invoke the Hub read_* method."""
    return getattr(hub, method)(*args, **kvargs)


class ModbusReadCache:
    """Wraps Modbus Hub and provide cached methods."""

    def __init__(self, hub):
        """Init the read cache."""
        self._hub = hub

    def __getattr__(self, attr):
        """Forward calls to the Hub object or use cached."""
        if attr not in CACHED_METHODS:
            return getattr(self._hub, attr)

        return partial(_read_cached, self._hub, attr, int(time.time()))
