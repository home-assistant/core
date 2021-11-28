"""The snmp component."""
from __future__ import annotations

import logging

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import Event
from homeassistant.helpers.reload import async_reload_integration_platforms

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the snmp integration."""

    async def _reload_config(call: Event) -> None:
        """Reload top-level + platforms."""
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, _reload_config
    )

    return True
