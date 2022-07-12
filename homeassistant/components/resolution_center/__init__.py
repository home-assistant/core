"""The resolution center integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import issue_handler, websocket_api
from .const import DOMAIN
from .issue_handler import ResolutionCenterFlow, async_create_issue, async_delete_issue
from .issue_registry import async_load as async_load_issue_registry

__all__ = ["DOMAIN", "ResolutionCenterFlow", "async_create_issue", "async_delete_issue"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Resolution Center."""
    hass.data[DOMAIN] = {}

    issue_handler.async_setup(hass)
    websocket_api.async_setup(hass)
    await async_load_issue_registry(hass)

    return True
