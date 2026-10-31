"""Services for the Remote Python Debugger integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, SERVICE_START
from .helpers import async_start_debugger


async def _debug_start(call: ServiceCall) -> None:
    """Enable asyncio debugging and start the debugger."""
    await async_start_debugger(call.hass)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Remote Python Debugger integration."""
    async_register_admin_service(
        hass, DOMAIN, SERVICE_START, _debug_start, schema=probatio.Schema({})
    )
