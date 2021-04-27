"""Config flow for SONOS."""
import pysonos

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    result = await hass.async_add_executor_job(pysonos.discover)
    return bool(result)


config_entry_flow.register_discovery_flow(
    DOMAIN, "Sonos", _async_has_devices, config_entries.CONN_CLASS_LOCAL_PUSH
)
