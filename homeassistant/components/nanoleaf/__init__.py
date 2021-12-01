"""The Nanoleaf integration."""
from __future__ import annotations

from aionanoleaf import InvalidToken, Nanoleaf, Unavailable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .hub import NanoleafHub

PLATFORMS = ["button", "light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf from a config entry."""
    nanoleaf = Nanoleaf(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN]
    )
    try:
        await nanoleaf.get_info()
    except Unavailable as err:
        raise ConfigEntryNotReady from err
    except InvalidToken as err:
        raise ConfigEntryAuthFailed from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = NanoleafHub(hass, nanoleaf)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub: NanoleafHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.unload()
    return True
