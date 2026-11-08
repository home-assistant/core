"""Constants for the Repairs integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .models import RepairsData

DOMAIN = "repairs"

DATA_REPAIRS: HassKey[RepairsData] = HassKey(DOMAIN)


class FlowType(StrEnum):
    """Flow types supported in `next_flow` of RepairsFlowResult."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
