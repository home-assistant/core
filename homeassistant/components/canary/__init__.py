"""Support for Canary devices."""
import asyncio
from datetime import timedelta
import logging

from canary.api import Api
from requests import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from .const import (
    CONF_FFMPEG_ARGUMENTS,
    DATA_CANARY,
    DATA_UNDO_UPDATE_LISTENER,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["alarm_control_panel", "camera", "sensor"]


async def async_setup(hass: HomeAssistantType, config: dict) -> bool:
    """Set up the Canary integration."""
    hass.data.setdefault(DOMAIN, {})

    if hass.config_entries.async_entries(DOMAIN):
        return True

    ffmpeg_arguments = DEFAULT_FFMPEG_ARGUMENTS
    if CAMERA_DOMAIN in config:
        camera_config = next(
            (item for item in config[CAMERA_DOMAIN] if item["platform"] == DOMAIN),
            None,
        )

        if camera_config:
            ffmpeg_arguments = camera_config.get(
                CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
            )

    if DOMAIN in config:
        if ffmpeg_arguments != DEFAULT_FFMPEG_ARGUMENTS:
            config[DOMAIN][CONF_FFMPEG_ARGUMENTS] = ffmpeg_arguments

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Canary from a config entry."""
    if not entry.options:
        options = {
            CONF_FFMPEG_ARGUMENTS: entry.data.get(
                CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
            ),
            CONF_TIMEOUT: entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    try:
        canary_data = await hass.async_add_executor_job(
            _get_canary_data_instance, entry
        )
    except (ConnectTimeout, HTTPError) as error:
        _LOGGER.error("Unable to connect to Canary service: %s", str(error))
        raise ConfigEntryNotReady from error

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CANARY: canary_data,
        DATA_UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
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
        hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistantType, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class CanaryData:
    """Manages the data retrieved from Canary API."""

    def __init__(self, api: Api):
        """Init the Canary data object."""
        self._api = api
        self._locations_by_id = {}
        self._readings_by_device_id = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Get the latest data from py-canary with a throttle."""
        self._update(**kwargs)

    def _update(self, **kwargs):
        """Get the latest data from py-canary."""
        for location in self._api.get_locations():
            location_id = location.location_id

            self._locations_by_id[location_id] = location

            for device in location.devices:
                if device.is_online:
                    self._readings_by_device_id[
                        device.device_id
                    ] = self._api.get_latest_readings(device.device_id)

    @property
    def locations(self):
        """Return a list of locations."""
        return self._locations_by_id.values()

    def get_location(self, location_id):
        """Return a location based on location_id."""
        return self._locations_by_id.get(location_id, [])

    def get_readings(self, device_id):
        """Return a list of readings based on device_id."""
        return self._readings_by_device_id.get(device_id, [])

    def get_reading(self, device_id, sensor_type):
        """Return reading for device_id and sensor type."""
        readings = self._readings_by_device_id.get(device_id, [])
        return next(
            (
                reading.value
                for reading in readings
                if reading.sensor_type == sensor_type
            ),
            None,
        )

    def set_location_mode(self, location_id, mode_name, is_private=False):
        """Set location mode."""
        self._api.set_location_mode(location_id, mode_name, is_private)
        self.update(no_throttle=True)

    def get_live_stream_session(self, device):
        """Return live stream session."""
        return self._api.get_live_stream_session(device)


def _get_canary_data_instance(entry: ConfigEntry) -> CanaryData:
    """Initialize a new instance of CanaryData."""
    canary = Api(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )

    canary_data = CanaryData(canary)
    canary_data.update()

    return canary_data
