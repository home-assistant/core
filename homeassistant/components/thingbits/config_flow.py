"""Config flow for ThingBits."""
import thingbits_ha

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    # Check if there are any devices that can be discovered in the network.
    devices = await hass.async_add_executor_job(thingbits_ha.discover)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "ThingBits", _async_has_devices)
