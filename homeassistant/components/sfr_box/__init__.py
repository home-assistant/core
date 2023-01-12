"""SFR Box."""
from __future__ import annotations

import asyncio

from sfrbox_api.bridge import SFRBox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS
from .coordinator import SFRDataUpdateCoordinator
from .models import DomainData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFR box as config entry."""
    box = SFRBox(ip=entry.data[CONF_HOST], client=get_async_client(hass))
    data = DomainData(
        dsl=SFRDataUpdateCoordinator(hass, box, "dsl", lambda b: b.dsl_get_info()),
        system=SFRDataUpdateCoordinator(
            hass, box, "system", lambda b: b.system_get_info()
        ),
    )
    tasks = [
        data.dsl.async_config_entry_first_refresh(),
        data.system.async_config_entry_first_refresh(),
    ]
    await asyncio.gather(*tasks)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    system_info = data.system.data
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, system_info.mac_addr)},
        name="SFR Box",
        model=system_info.product_id,
        sw_version=system_info.version_mainfirmware,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
