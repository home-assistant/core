"""Component for the Slide local API."""

from __future__ import annotations

from goslideapi import GoSlideLocal as SlideLocalApi

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant

from .models import SlideConfigEntry, SlideData

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: SlideConfigEntry) -> bool:
    """Set up the slide_local integration."""

    api_version = entry.data[CONF_API_VERSION]
    host = entry.data[CONF_HOST]
    mac = entry.data[CONF_MAC]
    password = entry.data[CONF_PASSWORD]

    api = SlideLocalApi()
    await api.slide_add(
        api_version,
        host,
        password,
    )

    entry.runtime_data = SlideData(api, api_version, host, mac, password)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
