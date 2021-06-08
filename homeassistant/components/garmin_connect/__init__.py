"""The Garmin Connect integration."""
from datetime import date
import logging

from garminconnect_aio import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_API, DATA_COORDINATOR, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Connect from a config entry."""

    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    websession = async_get_clientsession(hass)
    api = Garmin(websession, username, password)
    try:
        await api.login()
    except (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
    ) as err:
        _LOGGER.error("Error occurred during Garmin Connect login request: %s", err)
        return False
    except (GarminConnectConnectionError) as err:
        _LOGGER.error(
            "Connection error occurred during Garmin Connect login request: %s", err
        )
        raise ConfigEntryNotReady from err
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unknown error occurred during Garmin Connect login request")
        return False

    async def async_update_data():
        return await async_update_garmin_data(api)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=username,
        update_method=async_update_data,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_garmin_data(api):
    """Fetch data from API endpoint."""
    try:
        summary = await api.get_user_summary(date.today().isoformat())
        body = await api.get_body_composition(date.today().isoformat())
        alarms = await api.get_device_alarms()

        return {
            **summary,
            **body["totalAverage"],
            "nextAlarm": alarms,
        }

    except (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
        GarminConnectConnectionError,
    ) as err:
        _LOGGER.error("Error occurred during Garmin Connect update request: %s", err)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unknown error occurred during Garmin Connect update request")
