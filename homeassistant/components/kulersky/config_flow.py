"""Config flow for Kuler Sky."""

import logging

import pykulersky

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    # Check if there are any devices that can be discovered in the network.
    try:
        devices = await pykulersky.discover()
    except pykulersky.PykulerskyException as exc:
        _LOGGER.error("Unable to discover nearby Kuler Sky devices: %s", exc)
        return False
    return len(devices) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "Kuler Sky", _async_has_devices)
