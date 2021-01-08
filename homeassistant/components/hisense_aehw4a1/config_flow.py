"""Config flow for Hisense AEH-W4A1 integration."""
from pyaehw4a1.aehw4a1 import AehW4a1

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    aehw4a1_ip_addresses = await AehW4a1().discovery()
    return len(aehw4a1_ip_addresses) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Hisense AEH-W4A1", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
