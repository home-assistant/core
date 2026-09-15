"""Constants for the remote component."""

from enum import StrEnum
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
