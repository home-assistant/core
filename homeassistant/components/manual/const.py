"""Constants for the manual integration."""

from enum import StrEnum

DOMAIN = "manual"


class ManualEntityStateAttribute(StrEnum):
    """State attributes for manual alarm control panel entities."""

    NEXT_STATE = "next_state"
    PREVIOUS_STATE = "previous_state"
