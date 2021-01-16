"""Config flow for izone."""

import asyncio
import logging

from async_timeout import timeout

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DISPATCH_CONTROLLER_DISCOVERED, IZONE, TIMEOUT_DISCOVERY
from .discovery import async_start_discovery_service, async_stop_discovery_service

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass):

    controller_ready = asyncio.Event()

    @callback
    def dispatch_discovered(_):
        controller_ready.set()

    async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, dispatch_discovered)

    disco = await async_start_discovery_service(hass)

    try:
        async with timeout(TIMEOUT_DISCOVERY):
            await controller_ready.wait()
    except asyncio.TimeoutError:
        pass

    if not disco.pi_disco.controllers:
        await async_stop_discovery_service(hass)
        _LOGGER.debug("No controllers found")
        return False

    _LOGGER.debug("Controllers %s", disco.pi_disco.controllers)
    return True


config_entry_flow.register_discovery_flow(
    IZONE, "iZone Aircon", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
