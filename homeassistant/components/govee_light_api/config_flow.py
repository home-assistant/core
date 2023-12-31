"""Config flow for Govee Local API."""

from __future__ import annotations

import asyncio
import logging

from govee_local_api import GoveeController

from homeassistant.components import network
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import (
    CONF_LISENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    adapter = await network.async_get_source_ip(hass, network.PUBLIC_TARGET_IP)

    controller: GoveeController = GoveeController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_address=adapter,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    await controller.start()

    try:
        async with asyncio.timeout(delay=5):
            while not controller.devices:
                await asyncio.sleep(delay=1)
    except asyncio.TimeoutError:
        _LOGGER.debug("No devices found")

    devices_count = len(controller.devices)
    controller.clenaup()
    controller = None

    return devices_count > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Govee Lights - Local API", _async_has_devices
)
