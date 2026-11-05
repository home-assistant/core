"""Constants for the Repairs integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .update_report import UpdateReport

DOMAIN = "repairs"

DATA_UPDATE_REPORT: HassKey[UpdateReport] = HassKey("repairs_update_report")
UPDATE_REPORT_ISSUE_ID = "update_report"


class FlowType(StrEnum):
    """Flow types supported in `next_flow` of RepairsFlowResult."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
