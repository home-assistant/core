"""The Paperless-ngx integration."""

from __future__ import annotations

from typing import cast

from pypaperless import Paperless
from pypaperless.exceptions import InitializationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN

_PLATFORMS: list[Platform] = []

type PaperlessConfigEntry = ConfigEntry[Paperless]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Set up Paperless-ngx from a config entry."""

    data = cast(dict, entry.data)
    try:
        client = Paperless(url=data[CONF_HOST], token=data[CONF_ACCESS_TOKEN])
        await client.initialize()
    except OSError as err:
        if "Connect call failed" in str(err) or "Domain name not found" in str(err):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_host",
            ) from err
    except InitializationError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Unload a config entry."""
    client = entry.runtime_data
    await client.__aexit__(None, None, None)
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
