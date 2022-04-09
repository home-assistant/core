"""Constants for Synology DSM."""
from __future__ import annotations

from dataclasses import dataclass

from synology_dsm.api.core.security import SynoCoreSecurity
from synology_dsm.api.core.upgrade import SynoCoreUpgrade
from synology_dsm.api.storage.storage import SynoStorage
from synology_dsm.api.surveillance_station.const import SNAPSHOT_PROFILE_BALANCED

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.helpers.entity import EntityCategory, EntityDescription

DOMAIN = "synology_dsm"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]
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
CONF_SNAPSHOT_QUALITY = "snap_profile_type"

DEFAULT_USE_SSL = True
DEFAULT_VERIFY_SSL = False
DEFAULT_PORT = 5000
DEFAULT_PORT_SSL = 5001
# Options
DEFAULT_SCAN_INTERVAL = 15  # min
DEFAULT_TIMEOUT = 10  # sec
DEFAULT_SNAPSHOT_QUALITY = SNAPSHOT_PROFILE_BALANCED

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


# Binary sensors
UPGRADE_BINARY_SENSORS: tuple[SynologyDSMBinarySensorEntityDescription, ...] = (
    SynologyDSMBinarySensorEntityDescription(
        # Deprecated, scheduled to be removed in 2022.6 (#68664)
        api_key=SynoCoreUpgrade.API_KEY,
        key="update_available",
        name="Update Available",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SECURITY_BINARY_SENSORS: tuple[SynologyDSMBinarySensorEntityDescription, ...] = (
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoCoreSecurity.API_KEY,
        key="status",
        name="Security Status",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
)

STORAGE_DISK_BINARY_SENSORS: tuple[SynologyDSMBinarySensorEntityDescription, ...] = (
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_exceed_bad_sector_thr",
        name="Exceeded Max Bad Sectors",
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SynologyDSMBinarySensorEntityDescription(
        api_key=SynoStorage.API_KEY,
        key="disk_below_remain_life_thr",
        name="Below Min Remaining Life",
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
