"""Config flow for EHEIM Digital."""

from __future__ import annotations

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    return (
        await (await zeroconf.async_get_async_instance(hass)).async_get_service_info(
            "_http._tcp.local.", "eheimdigital._http._tcp.local."
        )
        is not None
    )


config_entry_flow.register_discovery_flow(DOMAIN, "EHEIM Digital", _async_has_devices)
