"""Constants for Glances component."""
from homeassistant.const import TEMP_CELSIUS

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
    "disk_use_percent": ["Disk used percent", "%", "mdi:harddisk"],
    "disk_use": ["Disk used", "GiB", "mdi:harddisk"],
    "disk_free": ["Disk free", "GiB", "mdi:harddisk"],
    "memory_use_percent": ["RAM used percent", "%", "mdi:memory"],
    "memory_use": ["RAM used", "MiB", "mdi:memory"],
    "memory_free": ["RAM free", "MiB", "mdi:memory"],
    "swap_use_percent": ["Swap used percent", "%", "mdi:memory"],
    "swap_use": ["Swap used", "GiB", "mdi:memory"],
    "swap_free": ["Swap free", "GiB", "mdi:memory"],
    "processor_load": ["CPU load", "15 min", "mdi:memory"],
    "process_running": ["Running", "Count", "mdi:memory"],
    "process_total": ["Total", "Count", "mdi:memory"],
    "process_thread": ["Thread", "Count", "mdi:memory"],
    "process_sleeping": ["Sleeping", "Count", "mdi:memory"],
    "cpu_use_percent": ["CPU used", "%", "mdi:memory"],
    "cpu_temp": ["CPU Temp", TEMP_CELSIUS, "mdi:thermometer"],
    "docker_active": ["Containers active", "", "mdi:docker"],
    "docker_cpu_use": ["Containers CPU used", "%", "mdi:docker"],
    "docker_memory_use": ["Containers RAM used", "MiB", "mdi:docker"],
}
