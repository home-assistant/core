"""Constants for the Repairs integration."""

from enum import StrEnum

DOMAIN = "repairs"


class FlowType(StrEnum):
    """Flow type supported in `next_flow` of RepairsFlowResult.

    This differs from homeassistant.config_entries.FlowType as the repairs flow
    will support RepairsFlows as the `next_flow` as well.
    """

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
    # REPAIRS_FLOW to be implemented in future PR
