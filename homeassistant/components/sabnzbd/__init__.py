"""Support for monitoring an SABnzbd NZB client."""
import logging

from pysabnzbd import SabnzbdApiException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PATH, CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_SPEED,
    DEFAULT_NAME,
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

SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_PATH): str,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SABnzbd component."""
    hass.data.setdefault(DOMAIN, {})

    if hass.config_entries.async_entries(DOMAIN):
        return True

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SabNzbd Component."""
    sab_api = await get_client(hass, entry.data)
    if not sab_api:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        KEY_API: sab_api,
        KEY_NAME: entry.data[CONF_NAME],
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    sab_api_data = SabnzbdApiData(sab_api)

    async def async_service_handler(service: ServiceCall) -> None:
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

    return True


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
