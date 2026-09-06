"""Config flow for Govee light local."""

import asyncio
from contextlib import suppress
import logging

from govee_local_api import GoveeController

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from . import async_get_listening_addresses
from .const import (
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)
from .coordinator import log_bound_addresses

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    listening_addresses = await async_get_listening_addresses(hass)
    if not listening_addresses:
        _LOGGER.debug("No enabled IPv4 addresses to listen on")
        return False

    controller: GoveeController = GoveeController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_addresses=listening_addresses,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISTENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    try:
        _LOGGER.debug("Starting discovery on %s", listening_addresses)
        await controller.start()
    except OSError as ex:
        _LOGGER.error("Start failed, errno: %d", ex.errno)
        return False

    log_bound_addresses(controller)

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not controller.devices:
                await asyncio.sleep(delay=1)
    except TimeoutError:
        _LOGGER.debug("No devices found")

    devices_count = len(controller.devices)
    cleanup_complete: asyncio.Event = controller.cleanup()
    with suppress(TimeoutError):
        await asyncio.wait_for(cleanup_complete.wait(), 1)

    return devices_count > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Govee light local", _async_has_devices
)
