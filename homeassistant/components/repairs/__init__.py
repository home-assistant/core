"""The repairs integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassDict

from . import issue_handler, websocket_api
from .const import DOMAIN, FlowType
from .issue_handler import FLOW_MANAGER, REPAIRS, ConfirmRepairFlow, RepairsFlowManager
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


def repairs_flow_manager(hass: HomeAssistant) -> RepairsFlowManager | None:
    """Return the repairs flow manager."""
    if (domain_data := hass.data.get(REPAIRS)) is None:
        return None

    return domain_data.get(FLOW_MANAGER)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""
    hass.data[REPAIRS] = HassDict()

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)

    return True
