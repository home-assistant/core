"""Constants for the Repairs integration."""

from enum import StrEnum

DOMAIN = "repairs"


class FlowType(StrEnum):
    """Flow types supported in `next_flow` of RepairsFlowResult."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
