"""Support for I2C MCP23017 chip."""

import threading

DOMAIN = "mcp23017"


class DeviceList:
    """Lockable device dictionary.

    This class enables thread-safe usage of multiple:
    - components within one device (unique initialization for each device iso for each component)
    - devices within a system (WAR: adafruit_bus_device.I3CDevice using thread-unsafe Lockable.try_lock() from adafruit_blinka)
    """

    def __init__(self):
        """Initialize the device dictionary and associated lock."""
        self._lock = threading.Lock()
        self._instances = {}

    def __enter__(self):
        """Acquire dictionary lock."""
        self._lock.acquire()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Release dictionary lock."""
        self._lock.release()

    def __contains__(self, key):
        """Handle 'in' operator."""
        return key in self._instances

    def __getitem__(self, key):
        """Handle 'object[key]' operation."""
        if key not in self._instances:
            return None
        return self._instances[key]

    def __setitem__(self, key, value):
        """Handle 'object[key]=value' operation."""
        self._instances[key] = value


DEVICES = DeviceList()
