"""Constants for the Repairs integration."""

from enum import StrEnum

DOMAIN = "repairs"


class FlowType(StrEnum):
    """FlowType to support additional next flow types for repairs."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
    REPAIRS_FLOW = "repairs_flow"
