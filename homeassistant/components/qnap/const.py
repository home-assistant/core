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
DEFAULT_NAME = "Qnap"
DEFAULT_PORT = 8080
DEFAULT_TIMEOUT = 5
DOMAIN = "qnap"


NOTIFICATION_ID = "qnap_notification"
NOTIFICATION_TITLE = "QNAP Sensor Setup"

_SYSTEM_MON_COND = {
    "status": ["Status", None, "mdi:checkbox-marked-circle-outline"],
    "system_temp": ["System Temperature", TEMP_CELSIUS, "mdi:thermometer"],
}
_CPU_MON_COND = {
    "cpu_temp": ["CPU Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "cpu_usage": ["CPU Usage", PERCENTAGE, "mdi:chip"],
}
_MEMORY_MON_COND = {
    "memory_free": ["Memory Available", DATA_GIBIBYTES, "mdi:memory"],
    "memory_used": ["Memory Used", DATA_GIBIBYTES, "mdi:memory"],
    "memory_percent_used": ["Memory Usage", PERCENTAGE, "mdi:memory"],
}
_NETWORK_MON_COND = {
    "network_link_status": ["Network Link", None, "mdi:checkbox-marked-circle-outline"],
    "network_tx": ["Network Up", DATA_RATE_MEBIBYTES_PER_SECOND, "mdi:upload"],
    "network_rx": ["Network Down", DATA_RATE_MEBIBYTES_PER_SECOND, "mdi:download"],
}
_DRIVE_MON_COND = {
    "drive_smart_status": ["SMART Status", None, "mdi:checkbox-marked-circle-outline"],
    "drive_temp": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
}
_VOLUME_MON_COND = {
    "volume_size_used": ["Used Space", DATA_GIBIBYTES, "mdi:chart-pie"],
    "volume_size_free": ["Free Space", DATA_GIBIBYTES, "mdi:chart-pie"],
    "volume_percentage_used": ["Volume Used", PERCENTAGE, "mdi:chart-pie"],
}

_MONITORED_CONDITIONS = (
    list(_SYSTEM_MON_COND)
    + list(_CPU_MON_COND)
    + list(_MEMORY_MON_COND)
    + list(_NETWORK_MON_COND)
    + list(_DRIVE_MON_COND)
    + list(_VOLUME_MON_COND)
)
