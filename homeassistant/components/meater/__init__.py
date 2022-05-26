"""The Meater Temperature Probe integration."""
from datetime import timedelta
import logging

import async_timeout
from meater import (
    AuthenticationError,
    MeaterApi,
    ServiceUnavailableError,
    TooManyRequestsError,
)
from meater.MeaterApi import MeaterProbe

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meater Temperature Probe from a config entry."""
    # Store an API object to access
    session = async_get_clientsession(hass)
    meater_api = MeaterApi(session)

    # Add the credentials
    try:
        _LOGGER.debug("Authenticating with the Meater API")
        await meater_api.authenticate(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except (ServiceUnavailableError, TooManyRequestsError) as err:
        raise ConfigEntryNotReady from err
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            f"Unable to authenticate with the Meater API: {err}"
        ) from err

    async def async_update_data() -> dict[str, MeaterProbe]:
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                devices: list[MeaterProbe] = await meater_api.get_all_devices()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("The API call wasn't authenticated") from err
        except TooManyRequestsError as err:
            raise UpdateFailed(
                "Too many requests have been made to the API, rate limiting is in place"
            ) from err

        return {device.id: device for device in devices}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="meater_api",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("known_probes", set())

    hass.data[DOMAIN][entry.entry_id] = {
        "api": meater_api,
        "coordinator": coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
