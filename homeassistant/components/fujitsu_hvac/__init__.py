"""The Fujitsu HVAC (based on Ayla IOT) integration."""
from __future__ import annotations

from asyncio import timeout
from contextlib import suppress

from ayla_iot_unofficial import AylaAuthError, new_ayla_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    API,
    API_TIMEOUT,
    CONF_EUROPE,
    DOMAIN,
    FGLAIR_APP_ID,
    FGLAIR_APP_SECRET,
)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fujitsu HVAC (based on Ayla IOT) from a config entry."""
    api = new_ayla_api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        FGLAIR_APP_ID,
        FGLAIR_APP_SECRET,
        europe=entry.data[CONF_EUROPE],
    )

    try:
        async with timeout(API_TIMEOUT):
            await api.async_sign_in()
    except TimeoutError as e:
        raise ConfigEntryNotReady("Timed out while connecting to Ayla IoT API") from e
    except AylaAuthError as e:
        raise ConfigEntryAuthFailed("Credentuials expired for Ayla IoT API") from e

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    with suppress(TimeoutError):
        async with timeout(API_TIMEOUT):
            await hass.data[DOMAIN][API].async_sign_out()

    hass.data[DOMAIN].pop(API)

    return unload_ok
