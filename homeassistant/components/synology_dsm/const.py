"""Constants for Synology DSM."""
# from synology_dsm.api.core.security import SynoCoreSecurity
# from synology_dsm.api.core.utilization import SynoCoreUtilization
# from synology_dsm.api.storage.storage import SynoStorage

from homeassistant.const import (
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    UNIT_PERCENTAGE,
)

DOMAIN = "synology_dsm"
PLATFORMS = ["binary_sensor", "sensor"]

BASE_NAME = "Synology"

# Entry keys
SYNO_API = "syno_api"
UNDO_UPDATE_LISTENER = "undo_update_listener"

# Configuration
CONF_SECURITY = "security"
CONF_VOLUMES = "volumes"

DEFAULT_SSL = True
DEFAULT_PORT = 5000
DEFAULT_PORT_SSL = 5001
# Options
DEFAULT_SECURITY = True
DEFAULT_SCAN_INTERVAL = 15  # min


ENTITY_NAME = "name"
ENTITY_UNIT = "unit"
ENTITY_ICON = "icon"
ENTITY_CLASS = "device_class"
ENTITY_ENABLE = "enable"

# Binary sensors
STORAGE_DISK_BINARY_SENSORS = {
    "storage:disk_exceed_bad_sector_thr": {
        ENTITY_NAME: "Exceeded Max Bad Sectors",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:test-tube",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "storage:disk_below_remain_life_thr": {
        ENTITY_NAME: "Below Min Remaining Life",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:test-tube",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
}

SECURITY_BINARY_SENSORS = {
    "security:status": {
        ENTITY_NAME: "Security status",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:checkbox-marked-circle-outline",
        ENTITY_CLASS: "safety",
        ENTITY_ENABLE: True,
    },
}

# Sensors
UTILISATION_SENSORS = {
    "utilisation:cpu_other_load": {
        ENTITY_NAME: "CPU Load (Other)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "utilisation:cpu_user_load": {
        ENTITY_NAME: "CPU Load (User)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:cpu_system_load": {
        ENTITY_NAME: "CPU Load (System)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "utilisation:cpu_total_load": {
        ENTITY_NAME: "CPU Load (Total)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:cpu_1min_load": {
        ENTITY_NAME: "CPU Load (1 min)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "utilisation:cpu_5min_load": {
        ENTITY_NAME: "CPU Load (5 min)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:cpu_15min_load": {
        ENTITY_NAME: "CPU Load (15 min)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chip",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:memory_real_usage": {
        ENTITY_NAME: "Memory Usage (Real)",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:memory_size": {
        ENTITY_NAME: "Memory Size",
        ENTITY_UNIT: DATA_MEGABYTES,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "utilisation:memory_cached": {
        ENTITY_NAME: "Memory Cached",
        ENTITY_UNIT: DATA_MEGABYTES,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "utilisation:memory_available_swap": {
        ENTITY_NAME: "Memory Available (Swap)",
        ENTITY_UNIT: DATA_MEGABYTES,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:memory_available_real": {
        ENTITY_NAME: "Memory Available (Real)",
        ENTITY_UNIT: DATA_MEGABYTES,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:memory_total_swap": {
        ENTITY_NAME: "Memory Total (Swap)",
        ENTITY_UNIT: DATA_MEGABYTES,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:memory_total_real": {
        ENTITY_NAME: "Memory Total (Real)",
        ENTITY_UNIT: DATA_MEGABYTES,
        ENTITY_ICON: "mdi:memory",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:network_up": {
        ENTITY_NAME: "Network Up",
        ENTITY_UNIT: DATA_RATE_KILOBYTES_PER_SECOND,
        ENTITY_ICON: "mdi:upload",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "utilisation:network_down": {
        ENTITY_NAME: "Network Down",
        ENTITY_UNIT: DATA_RATE_KILOBYTES_PER_SECOND,
        ENTITY_ICON: "mdi:download",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
}
STORAGE_VOL_SENSORS = {
    "storage:volume_status": {
        ENTITY_NAME: "Status",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:checkbox-marked-circle-outline",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "storage:volume_size_total": {
        ENTITY_NAME: "Total Size",
        ENTITY_UNIT: DATA_TERABYTES,
        ENTITY_ICON: "mdi:chart-pie",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "storage:volume_size_used": {
        ENTITY_NAME: "Used Space",
        ENTITY_UNIT: DATA_TERABYTES,
        ENTITY_ICON: "mdi:chart-pie",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "storage:volume_percentage_used": {
        ENTITY_NAME: "Volume Used",
        ENTITY_UNIT: UNIT_PERCENTAGE,
        ENTITY_ICON: "mdi:chart-pie",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "storage:volume_disk_temp_avg": {
        ENTITY_NAME: "Average Disk Temp",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:thermometer",
        ENTITY_CLASS: "temperature",
        ENTITY_ENABLE: True,
    },
    "storage:volume_disk_temp_max": {
        ENTITY_NAME: "Maximum Disk Temp",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:thermometer",
        ENTITY_CLASS: "temperature",
        ENTITY_ENABLE: False,
    },
}
STORAGE_DISK_SENSORS = {
    "storage:disk_smart_status": {
        ENTITY_NAME: "Status (Smart)",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:checkbox-marked-circle-outline",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: False,
    },
    "storage:disk_status": {
        ENTITY_NAME: "Status",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:checkbox-marked-circle-outline",
        ENTITY_CLASS: None,
        ENTITY_ENABLE: True,
    },
    "storage:disk_temp": {
        ENTITY_NAME: "Temperature",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:thermometer",
        ENTITY_CLASS: "temperature",
        ENTITY_ENABLE: True,
    },
}


TEMP_SENSORS_KEYS = ["volume_disk_temp_avg", "volume_disk_temp_max", "disk_temp"]
