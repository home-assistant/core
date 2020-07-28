"""The Bond integration."""
import asyncio
from asyncio import TimeoutError as AsyncIOTimeoutError
import logging

from aiohttp import ClientError, ClientTimeout
from bond_api import Bond

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING

from .const import DOMAIN
from .utils import BondHub

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["cover", "fan", "light", "switch"]
_API_TIMEOUT = SLOW_UPDATE_WARNING - 1


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Bond component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Bond from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_ACCESS_TOKEN]

    bond = Bond(host=host, token=token, timeout=ClientTimeout(total=_API_TIMEOUT))
    hub = BondHub(bond)
    try:
        await hub.setup()
    except (ClientError, AsyncIOTimeoutError, OSError) as error:
        raise ConfigEntryNotReady from error

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
