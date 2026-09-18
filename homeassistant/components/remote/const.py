"""Constants for the remote component."""

from enum import IntFlag, StrEnum
from typing import Final

DOMAIN: Final = "remote"


class RemoteEntityStateAttribute(StrEnum):
    """State attributes for remote entities."""

    ACTIVITY_LIST = "activity_list"
    CURRENT_ACTIVITY = "current_activity"


class RemoteEntityFeature(IntFlag):
    """Supported features of the remote entity."""

    LEARN_COMMAND = 1
    DELETE_COMMAND = 2
    ACTIVITY = 4
