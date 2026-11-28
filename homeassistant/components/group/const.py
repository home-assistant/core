"""Constants for the Group integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import Group
    from .registry import GroupIntegrationRegistry

CONF_HIDE_MEMBERS = "hide_members"
CONF_IGNORE_NON_NUMERIC = "ignore_non_numeric"

DOMAIN = "group"
DATA_COMPONENT: HassKey[EntityComponent[Group]] = HassKey(DOMAIN)
REG_KEY: HassKey[GroupIntegrationRegistry] = HassKey(f"{DOMAIN}_registry")
GROUP_ORDER: HassKey[int] = HassKey("group_order")

SERVICE_SET = "set"
SERVICE_REMOVE = "remove"

CONF_ALL = "all"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]


class GroupService(StrEnum):
    """Store keys for group services."""

    RELOAD = "reload"
    REMOVE = "remove"
    SET = "set"


class GroupServiceArgument(StrEnum):
    """Store keys for group service arguments."""

    ADD_ENTITIES = "add_entities"
    ALL = "all"
    ENTITIES = "entities"
    ICON = "icon"
    NAME = "name"
    OBJECT_ID = "object_id"
    REMOVE_ENTITIES = "remove_entities"


class GroupEntityStateAttribute(StrEnum):
    """State attributes for group entities."""

    AUTO = "auto"
    ENTITY_ID = "entity_id"
    ORDER = "order"
