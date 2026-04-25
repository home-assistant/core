"""Config flow for the ARWN integration."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN


async def _async_has_devices(_: HomeAssistant) -> bool:
    """MQTT is set as dependency, so that should be sufficient."""
    return True


class ArwnFlowHandler(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Handle ARWN config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the config flow."""
        super().__init__(DOMAIN, "Ambient Radio Weather Network", _async_has_devices)
