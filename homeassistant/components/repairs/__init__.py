"""The repairs integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassDict

from . import issue_handler, websocket_api
from .const import DOMAIN, REPAIRS, FlowType
from .issue_handler import (
    ConfirmRepairFlow,
    RepairsFlowManager,
    async_get,
    repairs_flow_manager,
)
from .models import RepairsFlow, RepairsFlowContext, RepairsFlowResult

__all__ = [
    "DOMAIN",
    "ConfirmRepairFlow",
    "FlowType",
    "RepairsFlow",
    "RepairsFlowContext",
    "RepairsFlowManager",
    "RepairsFlowResult",
    "async_get",
    "repairs_flow_manager",
]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""

    hass.data[REPAIRS] = HassDict()

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)

    return True
