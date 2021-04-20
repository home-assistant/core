"""Config flow for NEW_NAME."""
import my_pypi_dependency

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    # TODO Check if there are any devices that can be discovered in the network.
    devices = await hass.async_add_executor_job(my_pypi_dependency.discover)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "NEW_NAME", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN
)
