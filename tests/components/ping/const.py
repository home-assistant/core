"""Constants for tests."""
from icmplib import Host

BINARY_SENSOR_IMPORT_DATA = {
    "name": "test2",
    "host": "127.0.0.1",
    "count": 1,
    "scan_interval": 50,
}

NON_AVAILABLE_HOST_PING = Host("192.168.178.1", 10, [])
