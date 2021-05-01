"""Support for monitoring a Sense energy sensor."""
import asyncio
from datetime import timedelta
import logging

from sense_energy import (
    ASyncSenseable,
    SenseAPITimeoutException,
    SenseAuthenticationException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTIVE_UPDATE_RATE,
    DOMAIN,
    SENSE_DATA,
    SENSE_DEVICE_UPDATE,
    SENSE_DEVICES_DATA,
    SENSE_DISCOVERED_DEVICES_DATA,
    SENSE_TIMEOUT_EXCEPTIONS,
    SENSE_TRENDS_COORDINATOR,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


class SenseDevicesData:
    """Data for each sense device."""

    def __init__(self):
        """Create."""
        self._data_by_device = {}

    def set_devices_data(self, devices):
        """Store a device update."""
        self._data_by_device = {device["id"]: device for device in devices}

    def get_device_by_id(self, sense_device_id):
        """Get the latest device data."""
        return self._data_by_device.get(sense_device_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Sense from a config entry."""

    entry_data = entry.data
    email = entry_data[CONF_EMAIL]
    password = entry_data[CONF_PASSWORD]
    timeout = entry_data[CONF_TIMEOUT]

    client_session = async_get_clientsession(hass)

    gateway = ASyncSenseable(
        api_timeout=timeout, wss_timeout=timeout, client_session=client_session
    )
    gateway.rate_limit = ACTIVE_UPDATE_RATE

    try:
        await gateway.authenticate(email, password)
    except SenseAuthenticationException:
        _LOGGER.error("Could not authenticate with sense server")
        return False
    except SENSE_TIMEOUT_EXCEPTIONS as err:
        raise ConfigEntryNotReady from err

    sense_devices_data = SenseDevicesData()
    try:
        sense_discovered_devices = await gateway.get_discovered_device_data()
        await gateway.update_realtime()
    except SENSE_TIMEOUT_EXCEPTIONS as err:
        raise ConfigEntryNotReady from err

    trends_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Sense Trends {email}",
        update_method=gateway.update_trend_data,
        update_interval=timedelta(seconds=300),
    )

    # This can take longer than 60s and we already know
    # sense is online since get_discovered_device_data was
    # successful so we do it later.
    asyncio.create_task(trends_coordinator.async_request_refresh())

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        SENSE_DATA: gateway,
        SENSE_DEVICES_DATA: sense_devices_data,
        SENSE_TRENDS_COORDINATOR: trends_coordinator,
        SENSE_DISCOVERED_DEVICES_DATA: sense_discovered_devices,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def async_sense_update(_):
        """Retrieve latest state."""
        try:
            await gateway.update_realtime()
        except SenseAPITimeoutException:
            _LOGGER.error("Timeout retrieving data")

        data = gateway.get_realtime()
        if "devices" in data:
            sense_devices_data.set_devices_data(data["devices"])
        async_dispatcher_send(hass, f"{SENSE_DEVICE_UPDATE}-{gateway.sense_monitor_id}")

    remove_update_callback = async_track_time_interval(
        hass, async_sense_update, timedelta(seconds=ACTIVE_UPDATE_RATE)
    )

    @callback
    def _remove_update_callback_at_stop(event):
        remove_update_callback()

    entry.async_on_unload(remove_update_callback)
    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _remove_update_callback_at_stop
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
