"""Constants for Synology DSM."""
from __future__ import annotations

from dataclasses import dataclass

from synology_dsm.api.core.security import SynoCoreSecurity
from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from synology_dsm.api.core.utilization import SynoCoreUtilization
from synology_dsm.api.dsm.information import SynoDSMInformation
from synology_dsm.api.storage.storage import SynoStorage
from synology_dsm.api.surveillance_station import SynoSurveillanceStation

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_UPDATE,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ENTITY_CATEGORY_CONFIG,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import EntityDescription

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

# Services
SERVICE_REBOOT = "reboot"
SERVICE_SHUTDOWN = "shutdown"
SERVICES = [
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
]


@dataclass
class SynologyDSMRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class SynologyDSMEntityDescription(EntityDescription, SynologyDSMRequiredKeysMixin):
    """Generic Synology DSM entity description."""


@dataclass
class SynologyDSMBinarySensorEntityDescription(
    BinarySensorEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM binary sensor entity."""


@dataclass
class SynologyDSMSensorEntityDescription(
    SensorEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM sensor entity."""


@dataclass
class SynologyDSMSwitchEntityDescription(
    SwitchEntityDescription, SynologyDSMEntityDescription
):
    """Describes Synology DSM switch entity."""


# Binary sensors
UPGRADE_BINARY_SENSORS: tuple[SynologyDSMBinarySensorEntityDescription, ...] = (
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoCoreUpgrade.API_KEY,
        key="update_available",
        name="Update Available",
        device_class=DEVICE_CLASS_UPDATE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
)

SECURITY_BINARY_SENSORS: tuple[SynologyDSMBinarySensorEntityDescription, ...] = (
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoCoreSecurity.API_KEY,
        key="status",
        name="Security Status",
        device_class=DEVICE_CLASS_SAFETY,
    ),
)

STORAGE_DISK_BINARY_SENSORS: tuple[SynologyDSMBinarySensorEntityDescription, ...] = (
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_exceed_bad_sector_thr",
        name="Exceeded Max Bad Sectors",
        device_class=DEVICE_CLASS_SAFETY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_below_remain_life_thr",
        name="Below Min Remaining Life",
        device_class=DEVICE_CLASS_SAFETY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
)

# Sensors
UTILISATION_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_other_load",
        name="CPU Utilization (Other)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_user_load",
        name="CPU Utilization (User)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_system_load",
        name="CPU Utilization (System)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_total_load",
        name="CPU Utilization (Total)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chip",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_1min_load",
        name="CPU Load Average (1 min)",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        icon="mdi:chip",
        entity_registry_enabled_default=False,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_5min_load",
        name="CPU Load Average (5 min)",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        icon="mdi:chip",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="cpu_15min_load",
        name="CPU Load Average (15 min)",
        native_unit_of_measurement=ENTITY_UNIT_LOAD,
        icon="mdi:chip",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_real_usage",
        name="Memory Usage (Real)",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_size",
        name="Memory Size",
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_cached",
        name="Memory Cached",
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_available_swap",
        name="Memory Available (Swap)",
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:memory",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_available_real",
        name="Memory Available (Real)",
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:memory",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_total_swap",
        name="Memory Total (Swap)",
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:memory",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="memory_total_real",
        name="Memory Total (Real)",
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:memory",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="network_up",
        name="Upload Throughput",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:upload",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoCoreUtilization.API_KEY,
        key="network_down",
        name="Download Throughput",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:download",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)
STORAGE_VOL_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_status",
        name="Status",
        icon="mdi:checkbox-marked-circle-outline",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_size_total",
        name="Total Size",
        native_unit_of_measurement=DATA_TERABYTES,
        icon="mdi:chart-pie",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_size_used",
        name="Used Space",
        native_unit_of_measurement=DATA_TERABYTES,
        icon="mdi:chart-pie",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_percentage_used",
        name="Volume Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-pie",
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_disk_temp_avg",
        name="Average Disk Temp",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="volume_disk_temp_max",
        name="Maximum Disk Temp",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
)
STORAGE_DISK_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_smart_status",
        name="Status (Smart)",
        icon="mdi:checkbox-marked-circle-outline",
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_status",
        name="Status",
        icon="mdi:checkbox-marked-circle-outline",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_temp",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
)

INFORMATION_SENSORS: tuple[SynologyDSMSensorEntityDescription, ...] = (
    SynologyDSMSensorEntityDescription(
        api_key=SynoDSMInformation.API_KEY,
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SynologyDSMSensorEntityDescription(
        api_key=SynoDSMInformation.API_KEY,
        key="uptime",
        name="Last Boot",
        device_class=DEVICE_CLASS_TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
)

# Switch
SURVEILLANCE_SWITCH: tuple[SynologyDSMSwitchEntityDescription, ...] = (
    SynologyDSMSwitchEntityDescription(
        api_key=SynoSurveillanceStation.HOME_MODE_API_KEY,
        key="home_mode",
        name="Home Mode",
        icon="mdi:home-account",
        entity_category=ENTITY_CATEGORY_CONFIG,
    ),
)
