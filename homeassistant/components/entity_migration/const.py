"""Constants for the Entity Migration integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "entity_migration"

# Supported configuration types for scanning
CONFIG_TYPE_AUTOMATION: Final = "automation"
CONFIG_TYPE_SCRIPT: Final = "script"
CONFIG_TYPE_SCENE: Final = "scene"
CONFIG_TYPE_GROUP: Final = "group"
CONFIG_TYPE_PERSON: Final = "person"
CONFIG_TYPE_DASHBOARD: Final = "dashboard"

SUPPORTED_CONFIG_TYPES: Final = frozenset(
    {
        CONFIG_TYPE_AUTOMATION,
        CONFIG_TYPE_SCRIPT,
        CONFIG_TYPE_SCENE,
        CONFIG_TYPE_GROUP,
        CONFIG_TYPE_PERSON,
        CONFIG_TYPE_DASHBOARD,
    }
)

# Reference location identifiers
LOCATION_TRIGGER: Final = "trigger"
LOCATION_CONDITION: Final = "condition"
LOCATION_ACTION: Final = "action"
LOCATION_SEQUENCE: Final = "sequence"
LOCATION_ENTITY: Final = "entity"
LOCATION_MEMBER: Final = "member"
LOCATION_DEVICE_TRACKER: Final = "device_tracker"

# Service field names
ATTR_ENTITY_ID: Final = "entity_id"
