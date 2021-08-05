"""Constants for Synology DSM."""
from __future__ import annotations

from typing import Final, TypedDict

from synology_dsm.api.core.security import SynoCoreSecurity
from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.storage.storage import SynoStorage
from synology_dsm.api.surveillance_station import SynoSurveillanceStation

from homeassistant.components.binary_sensor import DEVICE_CLASS_SAFETY
from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
)


class EntityInfo(TypedDict):
    """TypedDict for EntityInfo."""

    name: str
    unit_of_measurement: str | None
    icon: str | None
    device_class: str | None
    state_class: str | None
    enable: bool


DOMAIN = "synology_dsm"
PLATFORMS = ["binary_sensor", "camera", "sensor", "switch"]
COORDINATOR_CAMERAS = "coordinator_cameras"
COORDINATOR_CENTRAL = "coordinator_central"
COORDINATOR_SWITCHES = "coordinator_switches"
SYSTEM_LOADED = "system_loaded"
EXCEPTION_DETAILS = "details"
EXCEPTION_UNKNOWN = "unknown"

# Entry keys
SYNO_API = "syno_api"
UNDO_UPDATE_LISTENER = "undo_update_listener"

# Configuration
CONF_SERIAL = "serial"
CONF_VOLUMES = "volumes"
CONF_DEVICE_TOKEN = "device_token"

DEFAULT_USE_SSL = True
DEFAULT_VERIFY_SSL = False
DEFAULT_PORT = 5000
DEFAULT_PORT_SSL = 5001
# Options
DEFAULT_SCAN_INTERVAL = 15  # min
DEFAULT_TIMEOUT = 10  # sec

ENTITY_UNIT_LOAD = "load"
ENTITY_ENABLE: Final = "enable"

# Services
SERVICE_REBOOT = "reboot"
SERVICE_SHUTDOWN = "shutdown"
SERVICES = [
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
]

# Entity keys should start with the API_KEY to fetch

# Binary sensors
UPGRADE_BINARY_SENSORS: dict[str, EntityInfo] = {
    f"{SynoCoreUpgrade.API_KEY}:update_available": {
        ATTR_NAME: "Update available",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:update",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
}

SECURITY_BINARY_SENSORS: dict[str, EntityInfo] = {
    f"{SynoCoreSecurity.API_KEY}:status": {
        ATTR_NAME: "Security status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_SAFETY,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
}

STORAGE_DISK_BINARY_SENSORS: dict[str, EntityInfo] = {
    f"{SynoStorage.API_KEY}:disk_exceed_bad_sector_thr": {
        ATTR_NAME: "Exceeded Max Bad Sectors",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_SAFETY,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoStorage.API_KEY}:disk_below_remain_life_thr": {
        ATTR_NAME: "Below Min Remaining Life",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_SAFETY,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
}

# Sensors
UTILISATION_SENSORS: dict[str, EntityInfo] = {
    f"{SynoCoreUtilization.API_KEY}:cpu_other_load": {
        ATTR_NAME: "CPU Utilization (Other)",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:cpu_user_load": {
        ATTR_NAME: "CPU Utilization (User)",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:cpu_system_load": {
        ATTR_NAME: "CPU Utilization (System)",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:cpu_total_load": {
        ATTR_NAME: "CPU Utilization (Total)",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:cpu_1min_load": {
        ATTR_NAME: "CPU Load Average (1 min)",
        ATTR_UNIT_OF_MEASUREMENT: ENTITY_UNIT_LOAD,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoCoreUtilization.API_KEY}:cpu_5min_load": {
        ATTR_NAME: "CPU Load Average (5 min)",
        ATTR_UNIT_OF_MEASUREMENT: ENTITY_UNIT_LOAD,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoCoreUtilization.API_KEY}:cpu_15min_load": {
        ATTR_NAME: "CPU Load Average (15 min)",
        ATTR_UNIT_OF_MEASUREMENT: ENTITY_UNIT_LOAD,
        ATTR_ICON: "mdi:chip",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_real_usage": {
        ATTR_NAME: "Memory Usage (Real)",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_size": {
        ATTR_NAME: "Memory Size",
        ATTR_UNIT_OF_MEASUREMENT: DATA_MEGABYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_cached": {
        ATTR_NAME: "Memory Cached",
        ATTR_UNIT_OF_MEASUREMENT: DATA_MEGABYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_available_swap": {
        ATTR_NAME: "Memory Available (Swap)",
        ATTR_UNIT_OF_MEASUREMENT: DATA_MEGABYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_available_real": {
        ATTR_NAME: "Memory Available (Real)",
        ATTR_UNIT_OF_MEASUREMENT: DATA_MEGABYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_total_swap": {
        ATTR_NAME: "Memory Total (Swap)",
        ATTR_UNIT_OF_MEASUREMENT: DATA_MEGABYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:memory_total_real": {
        ATTR_NAME: "Memory Total (Real)",
        ATTR_UNIT_OF_MEASUREMENT: DATA_MEGABYTES,
        ATTR_ICON: "mdi:memory",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:network_up": {
        ATTR_NAME: "Network Up",
        ATTR_UNIT_OF_MEASUREMENT: DATA_RATE_KILOBYTES_PER_SECOND,
        ATTR_ICON: "mdi:upload",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoCoreUtilization.API_KEY}:network_down": {
        ATTR_NAME: "Network Down",
        ATTR_UNIT_OF_MEASUREMENT: DATA_RATE_KILOBYTES_PER_SECOND,
        ATTR_ICON: "mdi:download",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
}
STORAGE_VOL_SENSORS: dict[str, EntityInfo] = {
    f"{SynoStorage.API_KEY}:volume_status": {
        ATTR_NAME: "Status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:checkbox-marked-circle-outline",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoStorage.API_KEY}:volume_size_total": {
        ATTR_NAME: "Total Size",
        ATTR_UNIT_OF_MEASUREMENT: DATA_TERABYTES,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoStorage.API_KEY}:volume_size_used": {
        ATTR_NAME: "Used Space",
        ATTR_UNIT_OF_MEASUREMENT: DATA_TERABYTES,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoStorage.API_KEY}:volume_percentage_used": {
        ATTR_NAME: "Volume Used",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ICON: "mdi:chart-pie",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoStorage.API_KEY}:volume_disk_temp_avg": {
        ATTR_NAME: "Average Disk Temp",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoStorage.API_KEY}:volume_disk_temp_max": {
        ATTR_NAME: "Maximum Disk Temp",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: None,
    },
}
STORAGE_DISK_SENSORS: dict[str, EntityInfo] = {
    f"{SynoStorage.API_KEY}:disk_smart_status": {
        ATTR_NAME: "Status (Smart)",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:checkbox-marked-circle-outline",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoStorage.API_KEY}:disk_status": {
        ATTR_NAME: "Status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:checkbox-marked-circle-outline",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
    f"{SynoStorage.API_KEY}:disk_temp": {
        ATTR_NAME: "Temperature",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
}

INFORMATION_SENSORS: dict[str, EntityInfo] = {
    f"{SynoDSMInformation.API_KEY}:temperature": {
        ATTR_NAME: "temperature",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    f"{SynoDSMInformation.API_KEY}:uptime": {
        ATTR_NAME: "last boot",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
        ENTITY_ENABLE: False,
        ATTR_STATE_CLASS: None,
    },
}

# Switch
SURVEILLANCE_SWITCH: dict[str, EntityInfo] = {
    f"{SynoSurveillanceStation.HOME_MODE_API_KEY}:home_mode": {
        ATTR_NAME: "home mode",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:home-account",
        ATTR_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ATTR_STATE_CLASS: None,
    },
}


TEMP_SENSORS_KEYS = [
    "volume_disk_temp_avg",
    "volume_disk_temp_max",
    "disk_temp",
    "temperature",
]
