"""Config Flow for Refoss integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DISCOVERY_TIMEOUT, DOMAIN
from .util import refoss_discovery_server


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    refoss_discovery = await refoss_discovery_server(hass)
    devices = await refoss_discovery.broadcast_msg(wait_for=DISCOVERY_TIMEOUT)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "Refoss", _async_has_devices)
