"""The Garmin Connect integration."""
from datetime import date
import logging

from garminconnect_ha import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import Throttle

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garmin Connect from a config entry."""

    username: str = entry.data[CONF_USERNAME]
    password: str = entry.data[CONF_PASSWORD]

    api = Garmin(username, password)

    try:
        await hass.async_add_executor_job(api.login)
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

    garmin_data = GarminConnectData(hass, api)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = garmin_data

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class GarminConnectData:
    """Define an object to hold sensor data."""

    def __init__(self, hass, client):
        """Initialize."""
        self.hass = hass
        self.client = client
        self.data = None

    @Throttle(DEFAULT_UPDATE_INTERVAL)
    async def async_update(self):
        """Update data via API wrapper."""
        today = date.today()

        try:
            summary = await self.hass.async_add_executor_job(
                self.client.get_user_summary, today.isoformat()
            )
            body = await self.hass.async_add_executor_job(
                self.client.get_body_composition, today.isoformat()
            )

            self.data = {
                **summary,
                **body["totalAverage"],
            }
            self.data["nextAlarm"] = await self.hass.async_add_executor_job(
                self.client.get_device_alarms
            )
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
            GarminConnectConnectionError,
        ) as err:
            _LOGGER.error(
                "Error occurred during Garmin Connect update requests: %s", err
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error occurred during Garmin Connect update requests"
            )
