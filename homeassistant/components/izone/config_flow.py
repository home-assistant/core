"""Config flow for izone."""

import logging

from async_timeout import timeout

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass):
    from .discovery import async_start_discovery_service

    disco = await async_start_discovery_service(hass)

    try:
        async with timeout(5):
            await disco.controller_ready.wait()
    except TimeoutError:
        pass

    _LOGGER.debug("Controllers %s", disco.controllers)

    return len(disco.controllers) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, 'iZone Aircon', _async_has_devices,
    config_entries.CONN_CLASS_LOCAL_POLL)
