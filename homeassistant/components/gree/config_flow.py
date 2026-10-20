"""Config flow for Gree."""

from greeclimate.discovery import Discovery

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DISCOVERY_TIMEOUT, DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return whether a one-shot discovery probe finds devices."""
    gree_discovery = Discovery(DISCOVERY_TIMEOUT)
    try:
        bcast_addr = list(await async_get_ipv4_broadcast_addresses(hass))
        devices = await gree_discovery.scan(
            wait_for=DISCOVERY_TIMEOUT, bcast_ifaces=bcast_addr
        )
        return len(devices) > 0
    finally:
        gree_discovery.close()


config_entry_flow.register_discovery_flow(DOMAIN, "Gree Climate", _async_has_devices)
