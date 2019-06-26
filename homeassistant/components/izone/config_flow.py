"""Config flow for izone."""

import logging
import asyncio

from async_timeout import timeout

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import IZONE, TIMEOUT_DISCOVERY


_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass):
    from .discovery import (
        async_start_discovery_service, async_stop_discovery_service)

    disco = await async_start_discovery_service(hass)

    try:
        async with timeout(TIMEOUT_DISCOVERY):
            await disco.controller_ready.wait()
    except asyncio.TimeoutError:
        pass

    if not disco.controllers:
        await async_stop_discovery_service(hass)
        _LOGGER.debug("No controllers found.")
        return False

    _LOGGER.debug("Controllers %s", disco.controllers)
    return True


config_entry_flow.register_discovery_flow(
    IZONE, 'iZone Aircon', _async_has_devices,
    config_entries.CONN_CLASS_LOCAL_POLL)
