"""The Hardware integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

from .const import DOMAIN
from .models import HardwareProtocol


async def async_process_hardware_platforms(hass: HomeAssistant) -> None:
    """Start processing hardware platforms."""
    hass.data[DOMAIN]["hardware_platform"] = {}

    await async_process_integration_platforms(hass, DOMAIN, _register_hardware_platform)


async def _register_hardware_platform(
    hass: HomeAssistant, integration_domain: str, platform: HardwareProtocol
) -> None:
    """Register a hardware platform."""
    if integration_domain == DOMAIN:
        return
    if not hasattr(platform, "async_info"):
        raise HomeAssistantError(f"Invalid hardware platform {platform}")
    hass.data[DOMAIN]["hardware_platform"][integration_domain] = platform
