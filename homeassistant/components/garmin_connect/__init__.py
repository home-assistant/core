"""The Garmin Connect integration."""
import asyncio
import logging
import voluptuous as vol
from datetime import date, timedelta
from typing import Any, Callable, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_ID
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, MIN_TIME_BETWEEN_UPDATES

from garminconnect import (
    Garmin,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
    GarminConnectAuthenticationError,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Garmin Connect component."""

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Garmin Connect from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        garmin_client = Garmin(username, password)
    except GarminConnectConnectionError:
        _LOGGER.error("Connection error occured during Garmin Connect Client init")
        return False
    except GarminConnectAuthenticationError:
        _LOGGER.error("Authentication error occured during Garmin Connect Client init")
        return False
    except GarminConnectTooManyRequestsError:
        _LOGGER.error(
            "Too many requests error occured during Garmin Connect Client init"
        )
        return False
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unknown error occured during Garmin Connect Client init")
        return False

    garmin_data = GarminConnectClient(hass, garmin_client)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = garmin_data

    try:
        await garmin_data.async_update()
    except ValueError as err:
        _LOGGER.error("Error while fetching data from Garmin Connect: %s", err)
        return

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # await garmin_data.async_update()

    # async def _interval_update(now=None) -> None:
    #     """Update Twente Milieu data."""
    #     await _update_twentemilieu(hass, unique_id)

    # async_track_time_interval(hass, _interval_update, SCAN_INTERVAL)

    # if hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
    #     unit_system = CONF_UNIT_SYSTEM_IMPERIAL
    # else:
    #     unit_system = CONF_UNIT_SYSTEM_METRIC

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


class GarminConnectClient:
    """Set up the Garmin Connect client."""

    def __init__(self, hass, client):
        """Initialize the client."""
        self.client = client
        self._hass: HomeAssistant = hass
        # self._update_interval: int = MIN_TIME_BETWEEN_UPDATES
        # self._unsubscribe_auto_updater: Optional[Callable] = None
        self.data = None

    # def set_update_interval(self, interval: int) -> None:
    #     """Set update interval."""
    #     _LOGGER.debug("Setting update interval: %d mins", interval)
    #     self._update_interval = interval
    #     if self._unsubscribe_auto_updater is not None:
    #         self._unsubscribe_auto_updater()

    #     delta = timedelta(minutes=interval)
    #     self._unsubscribe_auto_updater = async_track_time_interval(
    #         self._hass, self.update, delta
    #     )

    # async def update(self, unused=None):
    #     """Update data."""
    #     await self._hass.async_add_executor_job(self._update_data)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Fetch the latest data."""
        today = date.today()
        try:
            self.data = self.client.fetch_stats(today.isoformat())
        except GarminConnectConnectionError:
            _LOGGER.error("Connection error occured during Garmin Connect Client init")
            return
        except GarminConnectAuthenticationError:
            _LOGGER.error(
                "Authentication error occured during Garmin Connect Client init"
            )
            return
        except GarminConnectTooManyRequestsError:
            _LOGGER.error(
                "Too many requests error occured during Garmin Connect Client init"
            )
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error occured during Garmin Connect Client init")
            return
