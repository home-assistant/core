"""The template component."""

import logging

from homeassistant.const import SERVICE_RELOAD
from homeassistant.helpers.reload import async_reload_integration_platforms

from .const import DOMAIN, EVENT_TEMPLATE_RELOADED, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_reload_service(hass):
    """Create the reload service for the template domain."""

    if hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        return

    async def _reload_config(call):
        """Reload the template platform config."""

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        hass.bus.async_fire(EVENT_TEMPLATE_RELOADED, context=call.context)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, _reload_config
    )
