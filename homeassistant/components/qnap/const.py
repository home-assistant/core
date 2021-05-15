"""The Qnap constants."""
from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DATA_GIBIBYTES,
    DATA_RATE_MEBIBYTES_PER_SECOND,
    PERCENTAGE,
    TEMP_CELSIUS,
)

ATTR_DRIVE = "Drive"
ATTR_ENABLED = "Sensor Enabled"
ATTR_IP = "IP Address"
ATTR_MAC = "MAC Address"
ATTR_MASK = "Mask"
ATTR_MAX_SPEED = "Max Speed"
ATTR_MEMORY_SIZE = "Memory Size"
ATTR_MODEL = "Model"
ATTR_PACKETS_TX = "Packets (TX)"
ATTR_PACKETS_RX = "Packets (RX)"
ATTR_PACKETS_ERR = "Packets (Err)"
ATTR_SERIAL = "Serial #"
ATTR_TYPE = "Type"
ATTR_UPTIME = "Uptime"
ATTR_VOLUME_SIZE = "Volume Size"

CONF_DRIVES = "drives"
CONF_NICS = "nics"
CONF_VOLUMES = "volumes"
PLATFORMS = ["sensor"]
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
    "status": {
        ATTR_NAME: "Status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:checkbox-marked-circle-outline",
        ATTR_ENABLED: True,
    },
    "system_temp": {
        ATTR_NAME: "System Temperature",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ENABLED: True,
    },
}
_CPU_MON_COND = {
    "cpu_temp": {
        ATTR_NAME: "CPU Temperature",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ENABLED: False,
    },
    "cpu_usage": {
        ATTR_NAME: "CPU Usage",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chip",
        ATTR_ENABLED: True,
    },
}
_MEMORY_MON_COND = {
    "memory_free": {
        ATTR_NAME: "Memory Available",
        ATTR_UNIT_OF_MEASUREMENT: DATA_GIBIBYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_ENABLED: False,
    },
    "memory_used": {
        ATTR_NAME: "Memory Used",
        ATTR_UNIT_OF_MEASUREMENT: DATA_GIBIBYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_ENABLED: False,
    },
    "memory_percent_used": {
        ATTR_NAME: "Memory Usage",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:memory",
        ATTR_ENABLED: True,
    },
}
_NETWORK_MON_COND = {
    "network_link_status": {
        ATTR_NAME: "Network Link",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:checkbox-marked-circle-outline",
        ATTR_ENABLED: True,
    },
    "network_tx": {
        ATTR_NAME: "Network Up",
        ATTR_UNIT_OF_MEASUREMENT: DATA_RATE_MEBIBYTES_PER_SECOND,
        ATTR_ICON: "mdi:upload",
        ATTR_ENABLED: False,
    },
    "network_rx": {
        ATTR_NAME: "Network Down",
        ATTR_UNIT_OF_MEASUREMENT: DATA_RATE_MEBIBYTES_PER_SECOND,
        ATTR_ICON: "mdi:download",
        ATTR_ENABLED: False,
    },
}
_DRIVE_MON_COND = {
    "drive_smart_status": {
        ATTR_NAME: "SMART Status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:checkbox-marked-circle-outline",
        ATTR_ENABLED: True,
    },
    "drive_temp": {
        ATTR_NAME: "Temperature",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer",
        ATTR_ENABLED: False,
    },
}

_FOLDER_MON_COND = {
    "folder_size_used": {
        ATTR_NAME: "Used Space",
        ATTR_UNIT_OF_MEASUREMENT: DATA_GIBIBYTES,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_ENABLED: False,
    },
    "folder_percentage_used": {
        ATTR_NAME: "Folder Used",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_ENABLED: False,
    },
}

_VOLUME_MON_COND = {
    "volume_size_used": {
        ATTR_NAME: "Used Space",
        ATTR_UNIT_OF_MEASUREMENT: DATA_GIBIBYTES,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_ENABLED: False,
    },
    "volume_size_free": {
        ATTR_NAME: "Free Space",
        ATTR_UNIT_OF_MEASUREMENT: DATA_GIBIBYTES,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_ENABLED: False,
    },
    "volume_percentage_used": {
        ATTR_NAME: "Volume Used",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_ENABLED: True,
    },
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
