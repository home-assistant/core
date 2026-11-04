"""The repairs integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import issue_handler, websocket_api
from .const import DOMAIN, FlowType
from .issue_handler import ConfirmRepairFlow, RepairsFlowManager
from .models import RepairsFlow, RepairsFlowContext, RepairsFlowResult

__all__ = [
    "DOMAIN",
    "ConfirmRepairFlow",
    "FlowType",
    "RepairsFlow",
    "RepairsFlowContext",
    "RepairsFlowManager",
    "RepairsFlowResult",
    "repairs_flow_manager",
]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def repairs_flow_manager(hass: HomeAssistant) -> RepairsFlowManager:
    """Return the repairs flow manager."""
    if (
        domain_data := hass.data.get(DOMAIN)
    ) is None or "flow_manager" not in domain_data:
        raise HomeAssistantError("repairs flow manager is not available")

    flow_manager: RepairsFlowManager = domain_data["flow_manager"]
    return flow_manager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""
    hass.data[DOMAIN] = {}

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)

    return True
