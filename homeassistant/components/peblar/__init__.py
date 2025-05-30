"""Integration for Peblar EV chargers."""

from __future__ import annotations

import asyncio

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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import (
    PeblarConfigEntry,
    PeblarDataUpdateCoordinator,
    PeblarRuntimeData,
    PeblarUserConfigurationDataUpdateCoordinator,
    PeblarVersionDataUpdateCoordinator,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Set up Peblar from a config entry."""

    # Set up connection to the Peblar charger
    peblar = Peblar(
        host=entry.data[CONF_HOST],
        session=async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True)),
    )
    try:
        await peblar.login(password=entry.data[CONF_PASSWORD])
        system_information = await peblar.system_information()
        api = await peblar.rest_api(enable=True, access_mode=AccessMode.READ_WRITE)
    except PeblarConnectionError as err:
        raise ConfigEntryNotReady("Could not connect to Peblar charger") from err
    except PeblarAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except PeblarError as err:
        raise ConfigEntryNotReady(
            "Unknown error occurred while connecting to Peblar charger"
        ) from err

    # Setup the data coordinators
    meter_coordinator = PeblarDataUpdateCoordinator(hass, entry, api)
    user_configuration_coordinator = PeblarUserConfigurationDataUpdateCoordinator(
        hass, entry, peblar
    )
    version_coordinator = PeblarVersionDataUpdateCoordinator(hass, entry, peblar)
    await asyncio.gather(
        meter_coordinator.async_config_entry_first_refresh(),
        user_configuration_coordinator.async_config_entry_first_refresh(),
        version_coordinator.async_config_entry_first_refresh(),
    )

    # Store the runtime data
    entry.runtime_data = PeblarRuntimeData(
        data_coordinator=meter_coordinator,
        system_information=system_information,
        user_configuration_coordinator=user_configuration_coordinator,
        version_coordinator=version_coordinator,
    )

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Unload Peblar config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
