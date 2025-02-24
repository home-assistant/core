"""Constants for Synology DSM."""

from __future__ import annotations

from collections.abc import Callable

from aiohttp import ClientTimeout
from synology_dsm.api.surveillance_station.const import SNAPSHOT_PROFILE_BALANCED
from synology_dsm.exceptions import (
    SynologyDSMAPIErrorException,
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginDisabledAccountException,
    SynologyDSMLoginFailedException,
    SynologyDSMLoginInvalidException,
    SynologyDSMLoginPermissionDeniedException,
    SynologyDSMRequestException,
)

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN = "synology_dsm"
DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}_backup_agent_listeners"
)
ATTRIBUTION = "Data provided by Synology"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]
EXCEPTION_DETAILS = "details"
EXCEPTION_UNKNOWN = "unknown"

ISSUE_MISSING_BACKUP_SETUP = "missing_backup_setup"

# Configuration
CONF_SERIAL = "serial"
CONF_VOLUMES = "volumes"
CONF_DEVICE_TOKEN = "device_token"
CONF_SNAPSHOT_QUALITY = "snap_profile_type"
CONF_BACKUP_SHARE = "backup_share"
CONF_BACKUP_PATH = "backup_path"

DEFAULT_USE_SSL = True
DEFAULT_VERIFY_SSL = False
DEFAULT_PORT = 5000
DEFAULT_PORT_SSL = 5001
# Options
DEFAULT_TIMEOUT = ClientTimeout(total=60, connect=15)
DEFAULT_SNAPSHOT_QUALITY = SNAPSHOT_PROFILE_BALANCED
DEFAULT_BACKUP_PATH = "ha_backup"

ENTITY_UNIT_LOAD = "load"

SHARED_SUFFIX = "_shared"

# Signals
SIGNAL_CAMERA_SOURCE_CHANGED = "synology_dsm.camera_stream_source_changed"

# Services
SERVICE_REBOOT = "reboot"
SERVICE_SHUTDOWN = "shutdown"
SERVICES = [
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
]

SYNOLOGY_AUTH_FAILED_EXCEPTIONS = (
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginDisabledAccountException,
    SynologyDSMLoginInvalidException,
    SynologyDSMLoginPermissionDeniedException,
)

SYNOLOGY_CONNECTION_EXCEPTIONS = (
    SynologyDSMAPIErrorException,
    SynologyDSMLoginFailedException,
    SynologyDSMRequestException,
)
