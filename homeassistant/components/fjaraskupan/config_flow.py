"""Config flow for Fjäråskupan integration."""

from fjaraskupan import device_filter

from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_flow import register_discovery_flow

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    service_infos = async_discovered_service_info(hass)

    for service_info in service_infos:
        if device_filter(service_info.device, service_info.advertisement):
            return True

    return False


register_discovery_flow(DOMAIN, "Fjäråskupan", _async_has_devices)
