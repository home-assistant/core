"""Constants for the Repairs integration."""

from enum import StrEnum

from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.util.hass_dict import HassDict, HassKey

DOMAIN = "repairs"

REPAIRS: HassKey[HassDict] = HassKey(DOMAIN)
PLATFORMS: HassKey[LazyIntegrationPlatforms] = HassKey("platforms")


class FlowType(StrEnum):
    """Flow types supported in `next_flow` of RepairsFlowResult."""

    CONFIG_FLOW = "config_flow"
    OPTIONS_FLOW = "options_flow"
    CONFIG_SUBENTRIES_FLOW = "config_subentries_flow"
