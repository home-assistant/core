"""The WattTime integration."""
from __future__ import annotations

from datetime import timedelta

from aiowatttime import Client
from aiowatttime.emissions import RealTimeEmissionsResponseType
from aiowatttime.errors import InvalidCredentialsError, WattTimeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WattTime from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await Client.async_login(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid username/password") from err
    except WattTimeError as err:
        LOGGER.error("Error while authenticating with WattTime: %s", err)
        return False

    async def async_update_data() -> RealTimeEmissionsResponseType:
        """Get the latest realtime emissions data."""
        try:
            return await client.emissions.async_get_realtime_emissions(
                entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]
            )
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed("Invalid username/password") from err
        except WattTimeError as err:
            raise UpdateFailed(
                f"Error while requesting data from WattTime: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.title,
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_update_data,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
