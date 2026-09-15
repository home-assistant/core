"""Constants for the remote component."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import RemoteEntity


DOMAIN: Final = "remote"
DATA_COMPONENT: HassKey[EntityComponent[RemoteEntity]] = HassKey(DOMAIN)


class RemoteEntityStateAttribute(StrEnum):
    """State attributes for remote entities."""

    ACTIVITY_LIST = "activity_list"
    CURRENT_ACTIVITY = "current_activity"


class RemoteEntityFeature(IntFlag):
    """Supported features of the remote entity."""

    LEARN_COMMAND = 1
    DELETE_COMMAND = 2
    ACTIVITY = 4
