"""Constants for the Repairs integration."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .issue_handler import RepairsFlowManager
    from .models import RepairsProtocol

DOMAIN = "repairs"

REPAIRS: HassKey[RepairsData] = HassKey(DOMAIN)


@dataclass
class RepairsData:
    """Dataclass to hold HassKey data."""

    flow_manager: RepairsFlowManager
    platforms: LazyIntegrationPlatforms[RepairsProtocol]


class FlowType(StrEnum):
    """Flow types supported in `next_flow` of RepairsFlowResult."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
