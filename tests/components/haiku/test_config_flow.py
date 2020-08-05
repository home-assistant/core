"""Config flow for Haiku."""
# import my_pypi_dependency

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

DOMAIN = "haiku"


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    return True


config_entry_flow.register_discovery_flow(
    DOMAIN, "Haiku", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN
)
