"""Constants for the HEMS Echonet Lite integration."""

from __future__ import annotations

from datetime import timedelta
import re

from pyhems import EntityDefinition

from homeassistant.const import EntityCategory

DOMAIN = "echonet_lite"
ATTR_EPC = "epc"
CONF_INTERFACE = "interface"
CONF_ENABLE_EXPERIMENTAL = "enable_experimental"
DEFAULT_INTERFACE = "0.0.0.0"
DEFAULT_POLL_INTERVAL = 60
ISSUE_RUNTIME_CLIENT_ERROR = "runtime_client_error"
ISSUE_RUNTIME_INACTIVE = "runtime_inactive"
RUNTIME_MONITOR_INTERVAL = timedelta(minutes=1)
RUNTIME_MONITOR_MAX_SILENCE = timedelta(minutes=5)
DISCOVERY_INTERVAL = 60.0 * 60.0  # 1 hour

# ============================================================================
# ECHONET Lite class codes used by this integration
# ============================================================================
# Names and values come from the ECHONET Lite specification (Machine Readable
# Appendix). pyhems exposes the same metadata at runtime via
# ``DefinitionsRegistry``; these literals are kept here so that imports stay
# pure (no I/O at import time) and so the integration owns its own naming.
CLASS_CODE_HOME_AIR_CONDITIONER = 0x0130
CLASS_CODE_AIR_CLEANER = 0x0135
CLASS_CODE_HOUSEHOLD_SOLAR_POWER_GENERATION = 0x0279
CLASS_CODE_STORAGE_BATTERY = 0x027D
CLASS_CODE_SWITCH = 0x05FD  # Switch (supporting JEM-A/HA terminals)
CLASS_CODE_CONTROLLER = 0x05FF

# ============================================================================
# ECHONET Lite property codes (EPCs) used by this integration
# ============================================================================
# Common (super class, 0x80-0x9F) EPCs.
EPC_OPERATION_STATUS = 0x80
EPC_INSTALLATION_LOCATION = 0x81
EPC_MANUFACTURER_FAULT_CODE = 0x86
EPC_CURRENT_LIMIT = 0x87
EPC_FAULT_STATUS = 0x88
EPC_FAULT_DESCRIPTION = 0x89
EPC_MANUFACTURER_CODE = 0x8A
EPC_PRODUCT_CODE = 0x8C
EPC_SERIAL_NUMBER = 0x8D
EPC_POWER_SAVING_OPERATION = 0x8F
EPC_REMOTE_CONTROL_SETTING = 0x93
EPC_CURRENT_TIME = 0x97
EPC_CURRENT_DATE = 0x98
EPC_POWER_LIMIT = 0x99
EPC_CUMULATIVE_OPERATING_TIME = 0x9A
EPC_INF_PROPERTY_MAP = 0x9D
EPC_SET_PROPERTY_MAP = 0x9E
EPC_GET_PROPERTY_MAP = 0x9F

# Stable (non-experimental) device class codes
# These device classes have been verified with real hardware.
# Other device classes are considered experimental.
STABLE_CLASS_CODES: frozenset[int] = frozenset(
    {
        CLASS_CODE_HOME_AIR_CONDITIONER,
        CLASS_CODE_AIR_CLEANER,
        CLASS_CODE_HOUSEHOLD_SOLAR_POWER_GENERATION,
        CLASS_CODE_STORAGE_BATTERY,
        CLASS_CODE_SWITCH,
        CLASS_CODE_CONTROLLER,
    }
)


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case.

    MRA enum names use camelCase (e.g., 'automaticAirFlowDirection').
    HA uses snake_case for state keys (e.g., 'automatic_air_flow_direction').
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# ============================================================================
# EntityCategory inference
# ============================================================================
# Home Assistant distinguishes three tiers:
# - DIAGNOSTIC: fault / error / cumulative counters / identification, etc.
# - CONFIG: writable settings (thresholds, schedules, reservations, ...)
# - None: primary user-facing entities (e.g. temperature, power reading)
#
# Only the standardized common EPCs (0x80-0x9F) are classified here via the
# explicit ``ENTITY_CATEGORY_BY_EPC`` map. Device-specific EPCs (0xA0-0xEF)
# are intentionally left uncategorized because their meaning varies per
# device class and keyword-based inference is too error-prone.

# EPC -> EntityCategory for the standardized common EPCs (0x80-0x9F).
ENTITY_CATEGORY_BY_EPC: dict[int, EntityCategory] = {
    # DIAGNOSTIC: fault / identification
    EPC_MANUFACTURER_FAULT_CODE: EntityCategory.DIAGNOSTIC,
    EPC_FAULT_STATUS: EntityCategory.DIAGNOSTIC,
    EPC_FAULT_DESCRIPTION: EntityCategory.DIAGNOSTIC,
    EPC_CUMULATIVE_OPERATING_TIME: EntityCategory.DIAGNOSTIC,
    # CONFIG: installation / settings
    EPC_INSTALLATION_LOCATION: EntityCategory.CONFIG,
    EPC_CURRENT_LIMIT: EntityCategory.CONFIG,
    EPC_POWER_SAVING_OPERATION: EntityCategory.CONFIG,
    EPC_REMOTE_CONTROL_SETTING: EntityCategory.CONFIG,
    EPC_CURRENT_TIME: EntityCategory.CONFIG,
    EPC_CURRENT_DATE: EntityCategory.CONFIG,
    EPC_POWER_LIMIT: EntityCategory.CONFIG,
}


def infer_entity_category(
    entity_def: EntityDefinition,
) -> EntityCategory | None:
    """Return the :class:`EntityCategory` for ``entity_def`` or ``None``.

    Classification is driven solely by :data:`ENTITY_CATEGORY_BY_EPC`, which
    covers the standardized common EPCs (0x80-0x9F). Any other EPC returns
    ``None`` (primary user-facing entity).
    """
    return ENTITY_CATEGORY_BY_EPC.get(entity_def.epc)


def infer_entity_registry_enabled_default(
    entity_def: EntityDefinition,
) -> bool:
    """Return the default enabled state for ``entity_def`` in the registry.

    Diagnostic entities (fault codes, fault status, cumulative operating time,
    ...) are disabled by default so they do not clutter the UI and do not
    grow the recorder database. Users can opt in via the entity registry when
    the value is needed. This mirrors the convention used by other Home
    Assistant integrations for diagnostic entities.
    """
    return infer_entity_category(entity_def) is not EntityCategory.DIAGNOSTIC


__all__ = [
    "ATTR_EPC",
    "CLASS_CODE_AIR_CLEANER",
    "CLASS_CODE_CONTROLLER",
    "CLASS_CODE_HOME_AIR_CONDITIONER",
    "CLASS_CODE_HOUSEHOLD_SOLAR_POWER_GENERATION",
    "CLASS_CODE_STORAGE_BATTERY",
    "CLASS_CODE_SWITCH",
    "CONF_ENABLE_EXPERIMENTAL",
    "CONF_INTERFACE",
    "DEFAULT_INTERFACE",
    "DEFAULT_POLL_INTERVAL",
    "DISCOVERY_INTERVAL",
    "DOMAIN",
    "ENTITY_CATEGORY_BY_EPC",
    "EPC_CUMULATIVE_OPERATING_TIME",
    "EPC_CURRENT_DATE",
    "EPC_CURRENT_LIMIT",
    "EPC_CURRENT_TIME",
    "EPC_FAULT_DESCRIPTION",
    "EPC_FAULT_STATUS",
    "EPC_GET_PROPERTY_MAP",
    "EPC_INF_PROPERTY_MAP",
    "EPC_INSTALLATION_LOCATION",
    "EPC_MANUFACTURER_CODE",
    "EPC_MANUFACTURER_FAULT_CODE",
    "EPC_OPERATION_STATUS",
    "EPC_POWER_LIMIT",
    "EPC_POWER_SAVING_OPERATION",
    "EPC_PRODUCT_CODE",
    "EPC_REMOTE_CONTROL_SETTING",
    "EPC_SERIAL_NUMBER",
    "EPC_SET_PROPERTY_MAP",
    "ISSUE_RUNTIME_CLIENT_ERROR",
    "ISSUE_RUNTIME_INACTIVE",
    "RUNTIME_MONITOR_INTERVAL",
    "RUNTIME_MONITOR_MAX_SILENCE",
    "STABLE_CLASS_CODES",
    "camel_to_snake",
    "infer_entity_category",
    "infer_entity_registry_enabled_default",
]
