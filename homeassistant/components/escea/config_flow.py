"""Config flow for escea."""
import asyncio
from contextlib import suppress
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DISPATCH_CONTROLLER_DISCOVERED,
    DOMAIN,
    ESCEA_FIREPLACE,
    TIMEOUT_DISCOVERY,
)
from .discovery import async_start_discovery_service, async_stop_discovery_service

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    controller_ready = asyncio.Event()

    @callback
    def dispatch_discovered(_):
        controller_ready.set()

    remove_handler = async_dispatcher_connect(
        hass, DISPATCH_CONTROLLER_DISCOVERED, dispatch_discovered
    )

    discovery_service = await async_start_discovery_service(hass)

    with suppress(TimeoutError):
        async with asyncio.timeout(TIMEOUT_DISCOVERY):
            await controller_ready.wait()

    remove_handler()

    if not discovery_service.controllers:
        await async_stop_discovery_service(hass)
        _LOGGER.debug("No controllers found")
        return False

    _LOGGER.debug("Controllers %s", discovery_service.controllers)
    return True


config_entry_flow.register_discovery_flow(DOMAIN, ESCEA_FIREPLACE, _async_has_devices)
