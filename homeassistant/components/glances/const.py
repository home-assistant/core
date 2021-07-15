"""Constants for Glances component."""
import sys

from homeassistant.const import (
    DATA_GIBIBYTES,
    DATA_MEBIBYTES,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
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

if sys.maxsize > 2 ** 32:
    CPU_ICON = "mdi:cpu-64-bit"
else:
    CPU_ICON = "mdi:cpu-32-bit"

SENSOR_TYPES = {
    "disk_use_percent": ["fs", "used percent", PERCENTAGE, "mdi:harddisk", None],
    "disk_use": ["fs", "used", DATA_GIBIBYTES, "mdi:harddisk", None],
    "disk_free": ["fs", "free", DATA_GIBIBYTES, "mdi:harddisk", None],
    "memory_use_percent": ["mem", "RAM used percent", PERCENTAGE, "mdi:memory", None],
    "memory_use": ["mem", "RAM used", DATA_MEBIBYTES, "mdi:memory", None],
    "memory_free": ["mem", "RAM free", DATA_MEBIBYTES, "mdi:memory", None],
    "swap_use_percent": [
        "memswap",
        "Swap used percent",
        PERCENTAGE,
        "mdi:memory",
        None,
    ],
    "swap_use": ["memswap", "Swap used", DATA_GIBIBYTES, "mdi:memory", None],
    "swap_free": ["memswap", "Swap free", DATA_GIBIBYTES, "mdi:memory", None],
    "processor_load": ["load", "CPU load", "15 min", CPU_ICON, None],
    "process_running": ["processcount", "Running", "Count", CPU_ICON, None],
    "process_total": ["processcount", "Total", "Count", CPU_ICON, None],
    "process_thread": ["processcount", "Thread", "Count", CPU_ICON, None],
    "process_sleeping": ["processcount", "Sleeping", "Count", CPU_ICON, None],
    "cpu_use_percent": ["cpu", "CPU used", PERCENTAGE, CPU_ICON, None],
    "temperature_core": [
        "sensors",
        "Temperature",
        TEMP_CELSIUS,
        None,
        DEVICE_CLASS_TEMPERATURE,
    ],
    "temperature_hdd": [
        "sensors",
        "Temperature",
        TEMP_CELSIUS,
        None,
        DEVICE_CLASS_TEMPERATURE,
    ],
    "fan_speed": ["sensors", "Fan speed", "RPM", "mdi:fan", None],
    "battery": ["sensors", "Charge", PERCENTAGE, "mdi:battery", None],
    "docker_active": ["docker", "Containers active", "", "mdi:docker", None],
    "docker_cpu_use": ["docker", "Containers CPU used", PERCENTAGE, "mdi:docker", None],
    "docker_memory_use": [
        "docker",
        "Containers RAM used",
        DATA_MEBIBYTES,
        "mdi:docker",
        None,
    ],
}
