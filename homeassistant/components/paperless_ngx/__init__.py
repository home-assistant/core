"""The Paperless-ngx integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pypaperless import Paperless
from pypaperless.exceptions import InitializationError
from pypaperless.models import Tag

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type PaperlessConfigEntry = ConfigEntry[PaperlessData]


@dataclass
class PaperlessData:
    """Adguard data type."""

    client: Paperless
    inbox_tags: list[Tag]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Set up Paperless-ngx from a config entry."""
    data = cast(dict, entry.data)
    try:
        aiohttp_session = async_get_clientsession(hass)
        client = Paperless(
            url=data[CONF_HOST], token=data[CONF_ACCESS_TOKEN], session=aiohttp_session
        )
        await client.initialize()
        inbox_tags = [tag async for tag in client.tags if tag.is_inbox_tag]

    except OSError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_host",
        ) from err
    except InitializationError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = PaperlessData(client, inbox_tags)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
