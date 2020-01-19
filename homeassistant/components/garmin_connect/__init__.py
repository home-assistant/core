"""The Garmin Connect integration."""
import asyncio
import logging
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN

from garminconnect import (
    Garmin,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
    GarminConnectAuthenticationError,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
MIN_SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Garmin Connect component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Garmin Connect from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        garmin_client = Garmin(username, password)
    except (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
    ) as err:
        _LOGGER.error("Error occured during Garmin Connect setup: %s", err)
        return False
    except (GarminConnectConnectionError) as err:
        _LOGGER.error("Error occured during Garmin Connect setup: %s", err)
        raise PlatformNotReady
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unknown error occured during Garmin Connect setup")
        return False

    garmin_data = GarminConnectData(hass, garmin_client)
    hass.data[DOMAIN][entry.entry_id] = garmin_data

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class GarminConnectData:
    """Define an object to hold sensor data."""

    def __init__(self, hass, client):
        """Initialize."""
        self.client = client
        self.data = None

    @Throttle(MIN_SCAN_INTERVAL)
    async def async_update(self):
        """Update data via library."""
        today = date.today()

        try:
            self.data = self.client.get_stats(today.isoformat())
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
        ) as err:
            _LOGGER.error("Error occured during Garmin Connect stats update: %s", err)
            return
        except (GarminConnectConnectionError) as err:
            _LOGGER.error("Error occured during Garmin Connect stats update: %s", err)
            raise PlatformNotReady
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Unknown error occured during Garmin Connect stats update")
            return
