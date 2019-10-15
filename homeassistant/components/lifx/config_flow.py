"""Config flow flow LIFX."""
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from .const import DOMAIN


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    import aiolifx

    lifx_ip_addresses = await aiolifx.LifxScan(hass.loop).scan()
    return len(lifx_ip_addresses) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "LIFX", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
