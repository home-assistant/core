"""The Hardware integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN
from .models import HardwareProtocol


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Hardware."""
    hass.data[DOMAIN] = {"hardware_platform": {}}

    websocket_api.async_setup(hass)
    await async_process_integration_platforms(hass, DOMAIN, _register_hardware_platform)

    return True


async def _register_hardware_platform(
    hass: HomeAssistant, integration_domain: str, platform: HardwareProtocol
):
    """Register a hardware platform."""
    if not hasattr(platform, "async_info"):
        raise HomeAssistantError(f"Invalid hardware platform {platform}")
    hass.data[DOMAIN]["hardware_platform"][integration_domain] = platform
