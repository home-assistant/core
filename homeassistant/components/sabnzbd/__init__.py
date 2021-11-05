"""Support for monitoring an SABnzbd NZB client."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pysabnzbd import SabnzbdApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.discovery import SERVICE_SABNZBD
from homeassistant.components.sensor import SensorEntityDescription
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
_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


@dataclass
class SabnzbdRequiredKeysMixin:
    """Mixin for required keys."""

    field_name: str


@dataclass
class SabnzbdSensorEntityDescription(SensorEntityDescription, SabnzbdRequiredKeysMixin):
    """Describes Sabnzbd sensor entity."""


SENSOR_TYPES: tuple[SabnzbdSensorEntityDescription, ...] = (
    SabnzbdSensorEntityDescription(
        key="current_status",
        name="Status",
        field_name="status",
    ),
    SabnzbdSensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=DATA_RATE_MEGABYTES_PER_SECOND,
        field_name="kbpersec",
    ),
    SabnzbdSensorEntityDescription(
        key="queue_size",
        name="Queue",
        native_unit_of_measurement=DATA_MEGABYTES,
        field_name="mb",
    ),
    SabnzbdSensorEntityDescription(
        key="queue_remaining",
        name="Left",
        native_unit_of_measurement=DATA_MEGABYTES,
        field_name="mbleft",
    ),
    SabnzbdSensorEntityDescription(
        key="disk_size",
        name="Disk",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="diskspacetotal1",
    ),
    SabnzbdSensorEntityDescription(
        key="disk_free",
        name="Disk Free",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="diskspace1",
    ),
    SabnzbdSensorEntityDescription(
        key="queue_count",
        name="Queue Count",
        field_name="noofslots_total",
    ),
    SabnzbdSensorEntityDescription(
        key="day_size",
        name="Daily Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="day_size",
    ),
    SabnzbdSensorEntityDescription(
        key="week_size",
        name="Weekly Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="week_size",
    ),
    SabnzbdSensorEntityDescription(
        key="month_size",
        name="Monthly Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="month_size",
    ),
    SabnzbdSensorEntityDescription(
        key="total_size",
        name="Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="total_size",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.string}
)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PATH): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_SENSORS): vol.All(
                    cv.ensure_list, [vol.In(SENSOR_KEYS)]
                ),
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_check_sabnzbd(sab_api):
    """Check if we can reach SABnzbd."""

    try:
        await sab_api.check_available()
        return True
    except SabnzbdApiException:
        _LOGGER.error("Connection to SABnzbd API failed")
        return False

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SabNzbd Component."""
    sab_api = await get_client(hass, entry.data)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        KEY_API: sab_api,
        KEY_NAME: entry.data[CONF_NAME],
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async_setup_sabnzbd(hass, sab_api)

    async def sabnzbd_discovered(service, info):
        """Handle service discovery."""
        ssl = info.get("properties", {}).get("https", "0") == "1"
        await async_configure_sabnzbd(hass, info, ssl)

    discovery.async_listen(hass, SERVICE_SABNZBD, sabnzbd_discovered)

    if (conf := config.get(DOMAIN)) is not None:
        use_ssl = conf[CONF_SSL]
        name = conf.get(CONF_NAME)
        api_key = conf.get(CONF_API_KEY)
        await async_configure_sabnzbd(hass, conf, use_ssl, name, api_key)
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
