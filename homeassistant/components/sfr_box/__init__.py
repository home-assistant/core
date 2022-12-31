"""SFR Box."""
from __future__ import annotations

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS
from .coordinator import DslDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SFR box as config entry."""
    box = SFRBox(ip=entry.data[CONF_HOST], client=get_async_client(hass))
    try:
        system_info = await box.system_get_info()
    except SFRBoxError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_HOST]}"
        ) from err
    hass.data.setdefault(DOMAIN, {})

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, system_info.mac_addr)},
        name="SFR Box",
        model=system_info.product_id,
        sw_version=system_info.version_mainfirmware,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "box": box,
        "dsl_coordinator": DslDataUpdateCoordinator(hass, box),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
