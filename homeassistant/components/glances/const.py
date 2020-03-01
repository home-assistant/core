"""Constants for Glances component."""
from homeassistant.const import (
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)

DOMAIN = "glances"
CONF_VERSION = "version"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Glances"
DEFAULT_PORT = 61208
DEFAULT_VERSION = 3
DEFAULT_SCAN_INTERVAL = 60

DATA_UPDATED = "glances_data_updated"
SUPPORTED_VERSIONS = [2, 3]

SENSOR_TYPES = {
    "disk_use_percent": ["fs", "used percent", UNIT_PERCENTAGE, "mdi:harddisk"],
    "disk_use": ["fs", "used", DATA_GIBIBYTES, "mdi:harddisk"],
    "disk_free": ["fs", "free", DATA_GIBIBYTES, "mdi:harddisk"],
    "memory_use_percent": ["mem", "RAM used percent", UNIT_PERCENTAGE, "mdi:memory"],
    "memory_use": ["mem", "RAM used", DATA_MEBIBYTES, "mdi:memory"],
    "memory_free": ["mem", "RAM free", DATA_MEBIBYTES, "mdi:memory"],
    "swap_use_percent": ["memswap", "Swap used percent", UNIT_PERCENTAGE, "mdi:memory"],
    "swap_use": ["memswap", "Swap used", DATA_GIBIBYTES, "mdi:memory"],
    "swap_free": ["memswap", "Swap free", DATA_GIBIBYTES, "mdi:memory"],
    "processor_load": ["load", "CPU load", "15 min", "mdi:memory"],
    "process_running": ["processcount", "Running", "Count", "mdi:memory"],
    "process_total": ["processcount", "Total", "Count", "mdi:memory"],
    "process_thread": ["processcount", "Thread", "Count", "mdi:memory"],
    "process_sleeping": ["processcount", "Sleeping", "Count", "mdi:memory"],
    "cpu_use_percent": ["cpu", "CPU used", UNIT_PERCENTAGE, "mdi:memory"],
    "sensor_temp": ["sensors", "Temp", TEMP_CELSIUS, "mdi:thermometer"],
    "docker_active": ["docker", "Containers active", "", "mdi:docker"],
    "docker_cpu_use": ["docker", "Containers CPU used", UNIT_PERCENTAGE, "mdi:docker"],
    "docker_memory_use": [
        "docker",
        "Containers RAM used",
        DATA_MEBIBYTES,
        "mdi:docker",
    ],
}
