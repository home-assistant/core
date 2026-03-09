"""Constants for the Repairs integration."""

from enum import StrEnum

DOMAIN = "repairs"


class NextFlowType(StrEnum):
    """Extend FlowType to support additional next flow types."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
