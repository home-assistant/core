"""Support for monitoring an SABnzbd NZB client."""
from collections.abc import Callable
import logging

from pysabnzbd import SabnzbdApiException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SSL,
    CONF_URL,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_API_KEY,
    ATTR_SPEED,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SPEED_LIMIT,
    DEFAULT_SSL,
    DOMAIN,
    KEY_API,
    KEY_API_DATA,
    KEY_NAME,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
    SIGNAL_SABNZBD_UPDATED,
    UPDATE_INTERVAL,
)
from .sab import get_client
from .sensor import SENSOR_KEYS

PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)

SERVICES = (
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)

SCHEMA_SERVICE = vol.Schema(
    {
        vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string,
        vol.Required(ATTR_API_KEY): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.deprecated(CONF_HOST),
                cv.deprecated(CONF_PORT),
                cv.deprecated(CONF_SENSORS),
                cv.deprecated(CONF_SSL),
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_URL): str,
                    vol.Optional(CONF_PATH): str,
                    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_SENSORS): vol.All(
                        cv.ensure_list, [vol.In(SENSOR_KEYS)]
                    ),
                    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                },
            )
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


@callback
def async_get_entry_id_for_service_call(hass: HomeAssistant, call: ServiceCall) -> str:
    """Get the entry ID related to a service call (by device ID)."""
    call_data_api_key = call.data[ATTR_API_KEY]

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[ATTR_API_KEY] == call_data_api_key:
            return entry.entry_id

    raise ValueError(f"No api for API key: {call_data_api_key}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SabNzbd Component."""
    sab_api = await get_client(hass, entry.data)
    if not sab_api:
        raise ConfigEntryNotReady

    sab_api_data = SabnzbdApiData(sab_api)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        KEY_API: sab_api,
        KEY_API_DATA: sab_api_data,
        KEY_NAME: entry.data[CONF_NAME],
    }

    @callback
    def extract_api(func: Callable) -> Callable:
        """Define a decorator to get the correct api for a service call."""

        async def wrapper(call: ServiceCall) -> None:
            """Wrap the service function."""
            entry_id = async_get_entry_id_for_service_call(hass, call)
            api_data = hass.data[DOMAIN][entry_id][KEY_API_DATA]

            try:
                await func(call, api_data)
            except Exception as err:
                raise HomeAssistantError(
                    f"Error while executing {func.__name__}: {err}"
                ) from err

        return wrapper

    @extract_api
    async def async_pause_queue(call: ServiceCall, api: SabnzbdApiData) -> None:
        await api.async_pause_queue()

    @extract_api
    async def async_resume_queue(call: ServiceCall, api: SabnzbdApiData) -> None:
        await api.async_resume_queue()

    @extract_api
    async def async_set_queue_speed(call: ServiceCall, api: SabnzbdApiData) -> None:
        speed = call.data.get(ATTR_SPEED)
        await api.async_set_queue_speed(speed)

    for service, method in (
        (SERVICE_PAUSE, async_pause_queue),
        (SERVICE_RESUME, async_resume_queue),
        (SERVICE_SET_SPEED, async_set_queue_speed),
    ):

        if hass.services.has_service(DOMAIN, service):
            continue

        hass.services.async_register(DOMAIN, service, method, schema=SCHEMA_SERVICE)

    async def async_update_sabnzbd(now):
        """Refresh SABnzbd queue data."""
        try:
            await sab_api.refresh_data()
            async_dispatcher_send(hass, SIGNAL_SABNZBD_UPDATED, None)
        except SabnzbdApiException as err:
            _LOGGER.error(err)

    async_track_time_interval(hass, async_update_sabnzbd, UPDATE_INTERVAL)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Sabnzbd config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # If this is the last loaded instance of Sabnzbd, deregister any services
        # defined during integration setup:
        for service_name in SERVICES:
            hass.services.async_remove(DOMAIN, service_name)

    return unload_ok


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
