"""Config flow for Zerproc."""
import logging

import pyzerproc

from homeassistant.helpers import config_entry_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    try:
        devices = await pyzerproc.discover()
        return len(devices) > 0
    except pyzerproc.ZerprocException:
        _LOGGER.error("Unable to discover nearby Zerproc devices", exc_info=True)
        return False


config_entry_flow.register_discovery_flow(DOMAIN, "Zerproc", _async_has_devices)
