"""Constants for Glances component."""
import sys

from homeassistant.const import DATA_GIBIBYTES, DATA_MEBIBYTES, PERCENTAGE, TEMP_CELSIUS

DOMAIN = "glances"
CONF_VERSION = "version"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Glances"
DEFAULT_PORT = 61208
DEFAULT_VERSION = 3
DEFAULT_SCAN_INTERVAL = 60

DATA_UPDATED = "glances_data_updated"
SUPPORTED_VERSIONS = [2, 3]

if sys.maxsize > 2 ** 32:
    CPU_ICON = "mdi:cpu-64-bit"
else:
    CPU_ICON = "mdi:cpu-32-bit"

SENSOR_TYPES = {
    "disk_use_percent": ["fs", "used percent", PERCENTAGE, "mdi:harddisk"],
    "disk_use": ["fs", "used", DATA_GIBIBYTES, "mdi:harddisk"],
    "disk_free": ["fs", "free", DATA_GIBIBYTES, "mdi:harddisk"],
    "memory_use_percent": ["mem", "RAM used percent", PERCENTAGE, "mdi:memory"],
    "memory_use": ["mem", "RAM used", DATA_MEBIBYTES, "mdi:memory"],
    "memory_free": ["mem", "RAM free", DATA_MEBIBYTES, "mdi:memory"],
    "swap_use_percent": ["memswap", "Swap used percent", PERCENTAGE, "mdi:memory"],
    "swap_use": ["memswap", "Swap used", DATA_GIBIBYTES, "mdi:memory"],
    "swap_free": ["memswap", "Swap free", DATA_GIBIBYTES, "mdi:memory"],
    "processor_load": ["load", "CPU load", "15 min", CPU_ICON],
    "process_running": ["processcount", "Running", "Count", CPU_ICON],
    "process_total": ["processcount", "Total", "Count", CPU_ICON],
    "process_thread": ["processcount", "Thread", "Count", CPU_ICON],
    "process_sleeping": ["processcount", "Sleeping", "Count", CPU_ICON],
    "cpu_use_percent": ["cpu", "CPU used", PERCENTAGE, CPU_ICON],
    "sensor_temp": ["sensors", "Temp", TEMP_CELSIUS, "mdi:thermometer"],
    "docker_active": ["docker", "Containers active", "", "mdi:docker"],
    "docker_cpu_use": ["docker", "Containers CPU used", PERCENTAGE, "mdi:docker"],
    "docker_memory_use": [
        "docker",
        "Containers RAM used",
        DATA_MEBIBYTES,
        "mdi:docker",
    ],
}
