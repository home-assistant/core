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
ATTR_CYCLE = SelectServiceArgument.CYCLE
ATTR_OPTION = SelectServiceArgument.OPTION

ATTR_OPTIONS = SelectEntityAttribute.OPTIONS

SERVICE_SELECT_FIRST = SelectService.SELECT_FIRST
SERVICE_SELECT_LAST = SelectService.SELECT_LAST
SERVICE_SELECT_NEXT = SelectService.SELECT_NEXT
SERVICE_SELECT_OPTION = SelectService.SELECT_OPTION
SERVICE_SELECT_PREVIOUS = SelectService.SELECT_PREVIOUS
