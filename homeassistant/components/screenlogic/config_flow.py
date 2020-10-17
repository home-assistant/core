"""Config flow for Screenlogic."""
import screenlogicpy

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    # TODO Check if there are any devices that can be discovered in the network.
    devices = await hass.async_add_executor_job(screenlogicpy.discover)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Screenlogic", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)


class ScreenlogicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""