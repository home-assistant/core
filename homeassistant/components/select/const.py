"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "select"


class SelectEntityAttribute(StrEnum):
    """Select entity attributes."""

    OPTIONS = "options"


class SelectService(StrEnum):
    """Select services."""

    SELECT_FIRST = "select_first"
    SELECT_LAST = "select_last"
    SELECT_NEXT = "select_next"
    SELECT_OPTION = "select_option"
    SELECT_PREVIOUS = "select_previous"


class SelectServiceArgument(StrEnum):
    """Select service arguments."""

    CYCLE = "cycle"
    OPTION = "option"


CONF_CYCLE = "cycle"
CONF_OPTION = "option"

#
# Backwards compatibility / needs to be formally deprecated
#
ATTR_CYCLE = "cycle"
ATTR_OPTIONS = "options"

SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SELECT_NEXT = "select_next"
SERVICE_SELECT_PREVIOUS = "select_previous"
