"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "select"


class SelectEntityCapabilityAttribute(StrEnum):
    """Capability attributes for select entities."""

    OPTIONS = "options"


class SelectServiceArgument:
    """Select service arguments."""

    CYCLE = "cycle"
    OPTION = "option"


CONF_CYCLE = "cycle"
CONF_OPTION = "option"

#
# Deprecated constants
# They are single-use constants, or have been replaced by enums.
# They need to be formally deprecated when all usage is removed
# from core components
#
ATTR_CYCLE = SelectServiceArgument.CYCLE
ATTR_OPTION = SelectServiceArgument.OPTION
ATTR_OPTIONS = SelectEntityCapabilityAttribute.OPTIONS.value
SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SELECT_NEXT = "select_next"
# pylint: disable-next=home-assistant-duplicate-const
SERVICE_SELECT_OPTION = "select_option"
SERVICE_SELECT_PREVIOUS = "select_previous"
