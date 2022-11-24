"""The repairs integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import issue_handler, websocket_api
from .const import DOMAIN
from .issue_handler import ConfirmRepairFlow, RepairsFlowManager
from .models import RepairsFlow

__all__ = [
    "ConfirmRepairFlow",
    "DOMAIN",
    "repairs_flow_manager",
    "RepairsFlow",
    "RepairsFlowManager",
]


def repairs_flow_manager(hass: HomeAssistant) -> RepairsFlowManager | None:
    """Return the repairs flow manager."""
    if (domain_data := hass.data.get(DOMAIN)) is None:
        return None

    flow_manager: RepairsFlowManager | None = domain_data.get("flow_manager")
    return flow_manager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""
    hass.data[DOMAIN] = {}

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)

    return True
