"""The Bond integration."""
import asyncio

from bond_api import Bond

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .utils import BondHub

PLATFORMS = ["cover", "fan", "light", "switch"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Bond component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Bond from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_ACCESS_TOKEN]

    bond = Bond(host=host, token=token)
    hub = BondHub(bond)
    await hub.setup()
    hass.data[DOMAIN][entry.entry_id] = hub

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub.bond_id)},
        manufacturer="Olibra",
        name=hub.bond_id,
        model=hub.target,
        sw_version=hub.fw_ver,
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
