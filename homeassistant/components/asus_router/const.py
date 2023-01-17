"""Constants for Asus Router component."""

from __future__ import annotations

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    PERCENTAGE,
    Platform,
)
from homeassistant.helpers.entity import EntityCategory

from .dataclass import AREntityDescription, ARSensorDescription

# MAIN COMPONENT PARAMETERS

DOMAIN = "asus_router"
PLATFORMS = [
    Platform.SENSOR,
]
ROUTER = "router"

# ASUS CONSTANTS

RANGE_CORES = range(1, 9)  # maximum of 8 cores from 1 to 8

# GENERAL USAGE CONSTANTS -->

COORDINATOR = "coordinator"
FREE = "free"
HTTP = "http"
HTTPS = "https"
METHOD = "method"
NEXT = "next"
NO_SSL = "no_ssl"
SENSORS = "sensors"
SSL = "ssl"
TOTAL = "total"
UNIQUE_ID = "unique_id"
USAGE = "usage"
USED = "used"

# CONFIGURATION CONSTANTS & DEFAULTS -->

CONF_DEFAULT_PORT = 0
CONF_DEFAULT_PORTS = {NO_SSL: 80, SSL: 8443}
CONF_DEFAULT_SSL = True
CONF_DEFAULT_USERNAME = "admin"

# Options that require restarting the integration
CONF_REQUIRE_RELOAD = [
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
]

DEFAULT_UPDATE_INTERVAL = 30

# CONSTANTS BY MODULE -->

# __init__ constants
STOP_LISTENER = "stop_listener"

# Configuration flow
BASE = "base"
CONFIGS = "configs"
ERRORS = "errors"

RESULT_CANNOT_RESOLVE = "cannot_resolve"
RESULT_CONNECTION_REFUSED = "connection_refused"
RESULT_ERROR = "error"
RESULT_LOGIN_BLOCKED = "login_blocked"
RESULT_SUCCESS = "success"
RESULT_UNKNOWN = "unknown"
RESULT_WRONG_CREDENTIALS = "wrong_credentials"

STEP_CREDENTIALS = "credentials"
STEP_FIND = "find"
STEP_FINISH = "finish"

# Sensors constants
CORE = "core"
CPU = "cpu"
RAM = "ram"

SENSORS_CPU = [TOTAL, USED, USAGE]
SENSORS_RAM = [FREE, TOTAL, USED, USAGE]

DEFAULT_SENSORS: dict[str, list[str]] = {}

# ICONS -->
ICON_CPU = "mdi:cpu-32-bit"
ICON_RAM = "mdi:memory"

# ENTITY DESCRIPTIONS -->

STATIC_SENSORS: list[AREntityDescription] = [
    # CPU
    ARSensorDescription(
        key=f"{TOTAL}_{USAGE}",
        key_group=CPU,
        name=CPU.upper(),
        icon=ICON_CPU,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        extra_state_attributes={
            f"{num}_{USAGE}": f"{CORE}_{num}" for num in RANGE_CORES
        },
    ),
    # RAM
    ARSensorDescription(
        key=USAGE,
        key_group=RAM,
        name=RAM.upper(),
        icon=ICON_RAM,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        extra_state_attributes={
            FREE: FREE,
            TOTAL: TOTAL,
            USED: USED,
        },
    ),
]
