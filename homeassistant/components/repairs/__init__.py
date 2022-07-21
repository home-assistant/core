"""The repairs integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import issue_handler, websocket_api
from .const import DOMAIN
from .issue_handler import (
    async_create_issue,
    async_delete_issue,
    create_issue,
    delete_issue,
)
from .issue_registry import async_load as async_load_issue_registry
from .models import IssueSeverity, RepairsFlow

__all__ = [
    "async_create_issue",
    "async_delete_issue",
    "create_issue",
    "delete_issue",
    "DOMAIN",
    "IssueSeverity",
    "RepairsFlow",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Repairs."""
    hass.data[DOMAIN] = {}

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)
    await async_load_issue_registry(hass)

    return True
