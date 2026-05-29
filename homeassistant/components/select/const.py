"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "select"


class SelectEntityAttribute(StrEnum):
    """Select entity attributes."""

    OPTIONS = "options"


class SelectServiceArgument:
    """Select service arguments."""

    CYCLE = "cycle"
    OPTION = "option"


CONF_CYCLE = "cycle"
CONF_OPTION = "option"

#
# Backwards compatibility / needs to be formally deprecated
#
ATTR_CYCLE = SelectServiceArgument.CYCLE
ATTR_OPTION = SelectServiceArgument.OPTION

ATTR_OPTIONS = SelectEntityAttribute.OPTIONS.value

#
# Single-use constants / needs to be formally deprecated
#
SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SELECT_NEXT = "select_next"
# pylint: disable-next=home-assistant-duplicate-const
SERVICE_SELECT_OPTION = "select_option"
SERVICE_SELECT_PREVIOUS = "select_previous"
