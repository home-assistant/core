"""Support for monitoring a Sense energy sensor."""

from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import logging
from typing import Any

from sense_energy import (
    ASyncSenseable,
    SenseAuthenticationException,
    SenseMFARequiredException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_UPDATE_RATE,
    SENSE_CONNECT_EXCEPTIONS,
    SENSE_DEVICE_UPDATE,
    SENSE_TIMEOUT_EXCEPTIONS,
    SENSE_WEBSOCKET_EXCEPTIONS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
type SenseConfigEntry = ConfigEntry[SenseData]


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


@dataclass(kw_only=True, slots=True)
class SenseData:
    """Sense data type."""

    data: ASyncSenseable
    device_data: SenseDevicesData
    trends: DataUpdateCoordinator[None]
    discovered: list[dict[str, Any]]


async def async_setup_entry(hass: HomeAssistant, entry: SenseConfigEntry) -> bool:
    """Set up Sense from a config entry."""

    entry_data = entry.data
    email = entry_data[CONF_EMAIL]
    timeout = entry_data[CONF_TIMEOUT]

    access_token = entry_data.get("access_token", "")
    user_id = entry_data.get("user_id", "")
    device_id = entry_data.get("device_id", "")
    refresh_token = entry_data.get("refresh_token", "")
    monitor_id = entry_data.get("monitor_id", "")

    client_session = async_get_clientsession(hass)

    # Creating the AsyncSenseable object loads
    # ssl certificates which does blocking IO
    gateway = await hass.async_add_executor_job(
        partial(
            ASyncSenseable,
            api_timeout=timeout,
            wss_timeout=timeout,
            client_session=client_session,
        )
    )
    gateway.rate_limit = ACTIVE_UPDATE_RATE

    try:
        gateway.load_auth(access_token, user_id, device_id, refresh_token)
        gateway.set_monitor_id(monitor_id)
        await gateway.get_monitor_data()
    except (SenseAuthenticationException, SenseMFARequiredException) as err:
        _LOGGER.warning("Sense authentication expired")
        raise ConfigEntryAuthFailed(err) from err
    except SENSE_TIMEOUT_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            str(err) or "Timed out during authentication"
        ) from err
    except SENSE_CONNECT_EXCEPTIONS as err:
        raise ConfigEntryNotReady(str(err)) from err

    try:
        sense_discovered_devices = await gateway.get_discovered_device_data()
        await gateway.update_realtime()
    except SENSE_TIMEOUT_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            str(err) or "Timed out during realtime update"
        ) from err
    except SENSE_WEBSOCKET_EXCEPTIONS as err:
        raise ConfigEntryNotReady(str(err) or "Error during realtime update") from err

    async def _async_update_trend():
        """Update the trend data."""
        try:
            await gateway.update_trend_data()
        except (SenseAuthenticationException, SenseMFARequiredException) as err:
            _LOGGER.warning("Sense authentication expired")
            raise ConfigEntryAuthFailed(err) from err
        except SENSE_CONNECT_EXCEPTIONS as err:
            raise UpdateFailed(err) from err

    trends_coordinator: DataUpdateCoordinator[None] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Sense Trends {email}",
        update_method=_async_update_trend,
        update_interval=timedelta(seconds=300),
    )
    # Start out as unavailable so we do not report 0 data
    # until the update happens
    trends_coordinator.last_update_success = False

    # This can take longer than 60s and we already know
    # sense is online since get_discovered_device_data was
    # successful so we do it later.
    entry.async_create_background_task(
        hass,
        trends_coordinator.async_request_refresh(),
        "sense.trends-coordinator-refresh",
    )

    entry.runtime_data = SenseData(
        data=gateway,
        device_data=SenseDevicesData(),
        trends=trends_coordinator,
        discovered=sense_discovered_devices,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_sense_update(_):
        """Retrieve latest state."""
        try:
            await gateway.update_realtime()
        except SENSE_TIMEOUT_EXCEPTIONS as ex:
            _LOGGER.error("Timeout retrieving data: %s", ex)
        except SENSE_WEBSOCKET_EXCEPTIONS as ex:
            _LOGGER.error("Failed to update data: %s", ex)

        data = gateway.get_realtime()
        if "devices" in data:
            entry.runtime_data.device_data.set_devices_data(data["devices"])
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


async def async_unload_entry(hass: HomeAssistant, entry: SenseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
