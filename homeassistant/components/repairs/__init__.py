"""The repairs integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
    create_issue,
    delete_issue,
)
from homeassistant.helpers.typing import ConfigType

from . import issue_handler, websocket_api
from .const import DOMAIN
from .issue_handler import ConfirmRepairFlow
from .models import RepairsFlow

__all__ = [
    "async_create_issue",
    "async_delete_issue",
    "create_issue",
    "delete_issue",
    "DOMAIN",
    "ConfirmRepairFlow",
    "IssueSeverity",
    "RepairsFlow",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""
    hass.data[DOMAIN] = {}

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)

    return True
