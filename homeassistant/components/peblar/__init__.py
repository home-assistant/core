"""Integration for Peblar EV chargers."""

from __future__ import annotations

from aiohttp import CookieJar
from peblar import (
    AccessMode,
    Peblar,
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
)

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import PeblarConfigEntry, PeblarMeterDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Set up Peblar from a config entry."""

    peblar = Peblar(
        host=entry.data[CONF_HOST],
        session=async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True)),
    )
    try:
        await peblar.login(password=entry.data[CONF_PASSWORD])
        api = await peblar.rest_api(enable=True, access_mode=AccessMode.READ_WRITE)
    except PeblarConnectionError as err:
        raise ConfigEntryError("Could not connect to Peblar charger") from err
    except PeblarAuthenticationError as err:
        raise ConfigEntryError("Could not login to Peblar charger") from err
    except PeblarError as err:
        raise ConfigEntryError(
            "Unknown error occurred while connecting to Peblar charger"
        ) from err

    coordinator = PeblarMeterDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Unload Peblar config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
