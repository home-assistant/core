"""The Qnap constants."""
from homeassistant.const import (
    DATA_GIBIBYTES,
    DATA_RATE_MEBIBYTES_PER_SECOND,
    PERCENTAGE,
    TEMP_CELSIUS,
)

CONF_DRIVES = "drives"
CONF_NICS = "nics"
CONF_VOLUMES = "volumes"
COMPONENTS = ["sensor"]
DEFAULT_NAME = "QNAP"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 5
DOMAIN = "qnap"
DEFAULT_MONITORED_CONDITIONS = [
    "status",
    "system_temp",
    "cpu_temp",
    "cpu_usage",
    "memory_free",
    "memory_used",
    "memory_percent_used",
]

NOTIFICATION_ID = "qnap_notification"
NOTIFICATION_TITLE = "QNAP Sensor Setup"

_SYSTEM_MON_COND = {
    "status": ["Status", None, "mdi:checkbox-marked-circle-outline", True],
    "system_temp": ["System Temperature", TEMP_CELSIUS, "mdi:thermometer", True],
}
_CPU_MON_COND = {
    "cpu_temp": ["CPU Temperature", TEMP_CELSIUS, "mdi:thermometer", False],
    "cpu_usage": ["CPU Usage", PERCENTAGE, "mdi:chip", True],
}
_MEMORY_MON_COND = {
    "memory_free": ["Memory Available", DATA_GIBIBYTES, "mdi:memory", False],
    "memory_used": ["Memory Used", DATA_GIBIBYTES, "mdi:memory", False],
    "memory_percent_used": ["Memory Usage", PERCENTAGE, "mdi:memory", True],
}
_NETWORK_MON_COND = {
    "network_link_status": [
        "Network Link",
        None,
        "mdi:checkbox-marked-circle-outline",
        True,
    ],
    "network_tx": ["Network Up", DATA_RATE_MEBIBYTES_PER_SECOND, "mdi:upload", False],
    "network_rx": [
        "Network Down",
        DATA_RATE_MEBIBYTES_PER_SECOND,
        "mdi:download",
        False,
    ],
}
_DRIVE_MON_COND = {
    "drive_smart_status": [
        "SMART Status",
        None,
        "mdi:checkbox-marked-circle-outline",
        True,
    ],
    "drive_temp": ["Temperature", TEMP_CELSIUS, "mdi:thermometer", False],
}

_FOLDER_MON_COND = {
    "folder_size_used": ["Used Space", DATA_GIBIBYTES, "mdi:chart-pie", False],
    "folder_percentage_used": ["Folder Used", PERCENTAGE, "mdi:chart-pie", False],
}

_VOLUME_MON_COND = {
    "volume_size_used": ["Used Space", DATA_GIBIBYTES, "mdi:chart-pie", False],
    "volume_size_free": ["Free Space", DATA_GIBIBYTES, "mdi:chart-pie", False],
    "volume_percentage_used": ["Volume Used", PERCENTAGE, "mdi:chart-pie", True],
}

_MONITORED_CONDITIONS = (
    list(_SYSTEM_MON_COND)
    + list(_CPU_MON_COND)
    + list(_MEMORY_MON_COND)
    + list(_FOLDER_MON_COND)
    + list(_NETWORK_MON_COND)
    + list(_DRIVE_MON_COND)
    + list(_VOLUME_MON_COND)
)
