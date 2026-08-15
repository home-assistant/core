"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "select"


class SelectEntityCapabilityAttribute(StrEnum):
    """Capability attributes for select entities."""

    OPTIONS = "options"


ATTR_CYCLE = "cycle"
ATTR_OPTIONS = "options"

CONF_CYCLE = "cycle"
CONF_OPTION = "option"

SERVICE_SELECT_FIRST = "select_first"
SERVICE_SELECT_LAST = "select_last"
SERVICE_SELECT_NEXT = "select_next"
SERVICE_SELECT_PREVIOUS = "select_previous"
