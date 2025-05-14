"""The Paperless-ngx integration."""

from __future__ import annotations

from typing import cast

from pypaperless import Paperless
from pypaperless.exceptions import PaperlessError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS

type PaperlessConfigEntry = ConfigEntry[Paperless]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Set up Paperless-ngx from a config entry."""
    data = cast(dict, entry.data)
    try:
        aiohttp_session = async_get_clientsession(hass)
        client = Paperless(
            url=data[CONF_HOST], token=data[CONF_ACCESS_TOKEN], session=aiohttp_session
        )
        await client.initialize()

    except PaperlessError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unknown",
        ) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Unload paperless-ngx config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
