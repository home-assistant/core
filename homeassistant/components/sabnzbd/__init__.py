"""Support for monitoring an SABnzbd NZB client."""
import logging

from pysabnzbd import SabnzbdApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    DATA_GIGABYTES,
    DATA_MEGABYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_SPEED,
    DEFAULT_SPEED_LIMIT,
    DOMAIN,
    KEY_API,
    KEY_NAME,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
    SIGNAL_SABNZBD_UPDATED,
    UPDATE_INTERVAL,
)
from .sab import get_client

PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "current_status": ["Status", None, "status"],
    "speed": ["Speed", DATA_RATE_MEGABYTES_PER_SECOND, "kbpersec"],
    "queue_size": ["Queue", DATA_MEGABYTES, "mb"],
    "queue_remaining": ["Left", DATA_MEGABYTES, "mbleft"],
    "disk_size": ["Disk", DATA_GIGABYTES, "diskspacetotal1"],
    "disk_free": ["Disk Free", DATA_GIGABYTES, "diskspace1"],
    "queue_count": ["Queue Count", None, "noofslots_total"],
    "day_size": ["Daily Total", DATA_GIGABYTES, "day_size"],
    "week_size": ["Weekly Total", DATA_GIGABYTES, "week_size"],
    "month_size": ["Monthly Total", DATA_GIGABYTES, "month_size"],
    "total_size": ["Total", DATA_GIGABYTES, "total_size"],
}

SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string}
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SabNzbd Component."""
    sab_api = await get_client(hass, entry.data)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        KEY_API: sab_api,
        KEY_NAME: entry.data[CONF_NAME],
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async_setup_sabnzbd(hass, sab_api)

    return True


@callback
def async_setup_sabnzbd(hass, sab_api):
    """Set up SABnzbd sensors and services."""
    sab_api_data = SabnzbdApiData(sab_api)

    async def async_service_handler(service):
        """Handle service calls."""
        if service.service == SERVICE_PAUSE:
            await sab_api_data.async_pause_queue()
        elif service.service == SERVICE_RESUME:
            await sab_api_data.async_resume_queue()
        elif service.service == SERVICE_SET_SPEED:
            speed = service.data.get(ATTR_SPEED)
            await sab_api_data.async_set_queue_speed(speed)

    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE, async_service_handler, schema=vol.Schema({})
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RESUME, async_service_handler, schema=vol.Schema({})
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SPEED, async_service_handler, schema=SPEED_LIMIT_SCHEMA
    )

    async def async_update_sabnzbd(now):
        """Refresh SABnzbd queue data."""
        try:
            await sab_api.refresh_data()
            async_dispatcher_send(hass, SIGNAL_SABNZBD_UPDATED, None)
        except SabnzbdApiException as err:
            _LOGGER.error(err)

    async_track_time_interval(hass, async_update_sabnzbd, UPDATE_INTERVAL)


class SabnzbdApiData:
    """Class for storing/refreshing sabnzbd api queue data."""

    def __init__(self, sab_api):
        """Initialize component."""
        self.sab_api = sab_api

    async def async_pause_queue(self):
        """Pause Sabnzbd queue."""

        try:
            return await self.sab_api.pause_queue()
        except SabnzbdApiException as err:
            _LOGGER.error(err)
            return False

    async def async_resume_queue(self):
        """Resume Sabnzbd queue."""

        try:
            return await self.sab_api.resume_queue()
        except SabnzbdApiException as err:
            _LOGGER.error(err)
            return False

    async def async_set_queue_speed(self, limit):
        """Set speed limit for the Sabnzbd queue."""

        try:
            return await self.sab_api.set_speed_limit(limit)
        except SabnzbdApiException as err:
            _LOGGER.error(err)
            return False

    def get_queue_field(self, field):
        """Return the value for the given field from the Sabnzbd queue."""
        return self.sab_api.queue.get(field)
