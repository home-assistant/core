"""The motion_blinds component."""
import asyncio
from datetime import timedelta
import logging
from socket import timeout

from motionblinds import MotionMulticast
from motionblinds.motion_blinds import ParseException

from homeassistant import config_entries, core
from homeassistant.const import CONF_API_KEY, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_AVAILABLE,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    KEY_MULTICAST_LISTENER,
    MANUFACTURER,
    PLATFORMS,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_FAST,
)
from .gateway import ConnectMotionGateway

_LOGGER = logging.getLogger(__name__)


class DataUpdateCoordinatorMotionBlinds(DataUpdateCoordinator):
    """Class to manage fetching data from single endpoint."""

    def __init__(
        self,
        hass,
        logger,
        gateway,
        *,
        name,
        update_interval=None,
        update_method=None,
    ):
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_method=update_method,
            update_interval=update_interval,
        )

        self._gateway = gateway

    def update_gateway(self):
        """Call all updates using one async_add_executor_job."""
        data = {}

        try:
            self._gateway.Update()
        except (timeout, ParseException):
            # let the error be logged and handled by the motionblinds library
            data[KEY_GATEWAY] = {ATTR_AVAILABLE: False}
            return data
        else:
            data[KEY_GATEWAY] = {ATTR_AVAILABLE: True}

        for blind in self._gateway.device_list.values():
            try:
                blind.Update()
            except (timeout, ParseException):
                # let the error be logged and handled by the motionblinds library
                data[blind.mac] = {ATTR_AVAILABLE: False}
            else:
                data[blind.mac] = {ATTR_AVAILABLE: True}

        return data

    async def _async_update_data(self):
        """Fetch the latest data from the gateway and blinds."""
        data = await self.hass.async_add_executor_job(self.update_gateway)

        all_available = True
        for device in data.values():
            if not device[ATTR_AVAILABLE]:
                all_available = False
                break

        if all_available:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL)
        else:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)

        return data


def setup(hass: core.HomeAssistant, config: dict):
    """Set up the Motion Blinds component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the motion_blinds components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]

    # Create multicast Listener
    if KEY_MULTICAST_LISTENER not in hass.data[DOMAIN]:
        multicast = MotionMulticast()
        hass.data[DOMAIN][KEY_MULTICAST_LISTENER] = multicast
        # start listening for local pushes (only once)
        await hass.async_add_executor_job(multicast.Start_listen)

        # register stop callback to shutdown listening for local pushes
        def stop_motion_multicast(event):
            """Stop multicast thread."""
            _LOGGER.debug("Shutting down Motion Listener")
            multicast.Stop_listen()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_motion_multicast)

    # Connect to motion gateway
    multicast = hass.data[DOMAIN][KEY_MULTICAST_LISTENER]
    connect_gateway_class = ConnectMotionGateway(hass, multicast)
    if not await connect_gateway_class.async_connect_gateway(host, key):
        raise ConfigEntryNotReady
    motion_gateway = connect_gateway_class.gateway_device

    coordinator = DataUpdateCoordinatorMotionBlinds(
        hass,
        _LOGGER,
        motion_gateway,
        # Name of the data. For logging purposes.
        name=entry.title,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_GATEWAY: motion_gateway,
        KEY_COORDINATOR: coordinator,
    }

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, motion_gateway.mac)},
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
        model="Wi-Fi bridge",
        sw_version=motion_gateway.protocol,
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    if len(hass.data[DOMAIN]) == 1:
        # No motion gateways left, stop Motion multicast
        _LOGGER.debug("Shutting down Motion Listener")
        multicast = hass.data[DOMAIN].pop(KEY_MULTICAST_LISTENER)
        await hass.async_add_executor_job(multicast.Stop_listen)

    return unload_ok
