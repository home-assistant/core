"""The repairs integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN, FlowType
from .issue_handler import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowManager,
    RepairsFlowResult,
    async_get,
    async_setup as async_setup_issue_handler,
    repairs_flow_manager,
)

__all__ = [
    "DOMAIN",
    "ConfirmRepairFlow",
    "FlowType",
    "RepairsFlow",
    "RepairsFlowManager",
    "RepairsFlowResult",
    "async_get",
    "repairs_flow_manager",
]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""
    hass.data[DOMAIN] = {}

    async_setup_issue_handler(hass)
    websocket_api.async_setup(hass)

    return True
