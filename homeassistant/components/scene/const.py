"""Constants for the scene integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import BaseScene

DOMAIN: Final = "scene"
DATA_COMPONENT: HassKey[EntityComponent[BaseScene]] = HassKey(DOMAIN)


class SceneEntityStateAttribute(StrEnum):
    """State attributes for scene entities."""

    ENTITY_ID = "entity_id"
    ID = "id"


class SceneService(StrEnum):
    """Store keys for scene services."""

    APPLY = "apply"
    CREATE = "create"
    DELETE = "delete"
    RELOAD = "reload"
    TURN_ON = "turn_on"


class SceneServiceArgument(StrEnum):
    """Store keys for scene service arguments."""

    ENTITIES = "entities"
    SCENE_ID = "scene_id"
    SNAPSHOT_ENTITIES = "snapshot_entities"
    TRANSITION = "transition"
