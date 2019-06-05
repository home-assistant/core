"""Config flow for TP-Link."""
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from .const import DOMAIN


async def async_get_devices(hass):
    """Return if there are devices that can be discovered."""
    from pyHS100 import Discover

    def discover():
        devs = Discover.discover()
        return devs
    return await hass.async_add_executor_job(discover)


config_entry_flow.register_discovery_flow(DOMAIN,
                                          'TP-Link Smart Home',
                                          async_get_devices,
                                          config_entries.CONN_CLASS_LOCAL_POLL)
