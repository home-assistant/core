"""Support for monitoring a Sense energy sensor."""
import asyncio
from datetime import timedelta
import logging

from sense_energy import (
    ASyncSenseable,
    SenseAPITimeoutException,
    SenseAuthenticationException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ACTIVE_UPDATE_RATE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SENSE_DATA,
    SENSE_DEVICE_UPDATE,
    SENSE_DEVICES_DATA,
    SENSE_DISCOVERED_DEVICES_DATA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class SenseDevicesData:
    """Data for each sense device."""

    def __init__(self):
        """Create."""
        self._data_by_device = {}

    def set_devices_data(self, devices):
        """Store a device update."""
        self._data_by_device = {}
        for device in devices:
            self._data_by_device[device["id"]] = device

    def get_device_by_id(self, sense_device_id):
        """Get the latest device data."""
        return self._data_by_device.get(sense_device_id)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Sense component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)
    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_EMAIL: conf[CONF_EMAIL],
                CONF_PASSWORD: conf[CONF_PASSWORD],
                CONF_TIMEOUT: conf[CONF_TIMEOUT],
            },
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Sense from a config entry."""

    entry_data = entry.data
    email = entry_data[CONF_EMAIL]
    password = entry_data[CONF_PASSWORD]
    timeout = entry_data[CONF_TIMEOUT]

    gateway = ASyncSenseable(api_timeout=timeout, wss_timeout=timeout)
    gateway.rate_limit = ACTIVE_UPDATE_RATE

    try:
        await gateway.authenticate(email, password)
    except SenseAuthenticationException:
        _LOGGER.error("Could not authenticate with sense server")
        return False
    except SenseAPITimeoutException:
        raise ConfigEntryNotReady

    sense_devices_data = SenseDevicesData()
    sense_discovered_devices = await gateway.get_discovered_device_data()

    hass.data[DOMAIN][entry.entry_id] = {
        SENSE_DATA: gateway,
        SENSE_DEVICES_DATA: sense_devices_data,
        SENSE_DISCOVERED_DEVICES_DATA: sense_discovered_devices,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def async_sense_update(now):
        """Retrieve latest state."""
        try:
            await gateway.update_realtime()
        except SenseAPITimeoutException:
            _LOGGER.error("Timeout retrieving data")

        data = gateway.get_realtime()
        if "devices" in data:
            sense_devices_data.set_devices_data(data["devices"])
        async_dispatcher_send(hass, f"{SENSE_DEVICE_UPDATE}-{gateway.sense_monitor_id}")

    hass.data[DOMAIN][entry.entry_id][
        "track_time_remove_callback"
    ] = async_track_time_interval(
        hass, async_sense_update, timedelta(seconds=ACTIVE_UPDATE_RATE)
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
    track_time_remove_callback = hass.data[DOMAIN][entry.entry_id][
        "track_time_remove_callback"
    ]
    track_time_remove_callback()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
