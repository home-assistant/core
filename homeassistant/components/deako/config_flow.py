"""Config flow for deako."""

from pydeako.discover import DeakoDiscoverer, DevicesNotFoundException

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN, NAME


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    _zc = await zeroconf.async_get_instance(hass)
    discoverer = DeakoDiscoverer(_zc)

    try:
        await discoverer.get_address()
    except DevicesNotFoundException:
        return False
    else:
        # address exists, there's at least one device
        return True


config_entry_flow.register_discovery_flow(DOMAIN, NAME, _async_has_devices)
