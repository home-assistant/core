"""Config flow for Wemo."""
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from . import DOMAIN


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    import pywemo

    return bool(pywemo.discover_devices())


config_entry_flow.register_discovery_flow(
    DOMAIN, "Wemo", _async_has_devices, config_entries.CONN_CLASS_LOCAL_PUSH
)
