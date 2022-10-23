"""The motion_blinds component."""
import asyncio
from datetime import timedelta
import logging
from socket import timeout
from typing import TYPE_CHECKING

from motionblinds import DEVICE_TYPES_WIFI, AsyncMotionMulticast, ParseException

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_AVAILABLE,
    CONF_INTERFACE,
    CONF_WAIT_FOR_PUSH,
    DEFAULT_INTERFACE,
    DEFAULT_WAIT_FOR_PUSH,
    DOMAIN,
    KEY_API_LOCK,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    KEY_MULTICAST_LISTENER,
    KEY_SETUP_LOCK,
    KEY_UNSUB_STOP,
    KEY_VERSION,
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
        coordinator_info,
        *,
        name,
        update_interval=None,
        update_method=None,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_method=update_method,
            update_interval=update_interval,
        )

        self.api_lock = coordinator_info[KEY_API_LOCK]
        self._gateway = coordinator_info[KEY_GATEWAY]
        self._wait_for_push = coordinator_info[CONF_WAIT_FOR_PUSH]

    def update_gateway(self):
        """Fetch data from gateway."""
        try:
            self._gateway.Update()
        except (timeout, ParseException):
            # let the error be logged and handled by the motionblinds library
            return {ATTR_AVAILABLE: False}
        else:
            return {ATTR_AVAILABLE: True}

    def update_blind(self, blind):
        """Fetch data from a blind."""
        try:
            if self._wait_for_push:
                blind.Update()
            else:
                blind.Update_trigger()
        except (timeout, ParseException):
            # let the error be logged and handled by the motionblinds library
            return {ATTR_AVAILABLE: False}
        else:
            return {ATTR_AVAILABLE: True}

    async def _async_update_data(self):
        """Fetch the latest data from the gateway and blinds."""
        data = {}

        async with self.api_lock:
            data[KEY_GATEWAY] = await self.hass.async_add_executor_job(
                self.update_gateway
            )

        for blind in self._gateway.device_list.values():
            await asyncio.sleep(1.5)
            async with self.api_lock:
                data[blind.mac] = await self.hass.async_add_executor_job(
                    self.update_blind, blind
                )

        all_available = all(device[ATTR_AVAILABLE] for device in data.values())
        if all_available:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL)
        else:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)

        return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the motion_blinds components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    setup_lock = hass.data[DOMAIN].setdefault(KEY_SETUP_LOCK, asyncio.Lock())
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]
    multicast_interface = entry.data.get(CONF_INTERFACE, DEFAULT_INTERFACE)
    wait_for_push = entry.options.get(CONF_WAIT_FOR_PUSH, DEFAULT_WAIT_FOR_PUSH)

    # Create multicast Listener
    async with setup_lock:
        if KEY_MULTICAST_LISTENER not in hass.data[DOMAIN]:
            # check multicast interface
            check_multicast_class = ConnectMotionGateway(
                hass, interface=multicast_interface
            )
            working_interface = await check_multicast_class.async_check_interface(
                host, key
            )
            if working_interface != multicast_interface:
                data = {**entry.data, CONF_INTERFACE: working_interface}
                hass.config_entries.async_update_entry(entry, data=data)
                _LOGGER.debug(
                    "Motion Blinds interface updated from %s to %s, "
                    "this should only occur after a network change",
                    multicast_interface,
                    working_interface,
                )

            multicast = AsyncMotionMulticast(interface=working_interface)
            hass.data[DOMAIN][KEY_MULTICAST_LISTENER] = multicast
            # start listening for local pushes (only once)
            await multicast.Start_listen()

            # register stop callback to shutdown listening for local pushes
            def stop_motion_multicast(event):
                """Stop multicast thread."""
                _LOGGER.debug("Shutting down Motion Listener")
                multicast.Stop_listen()

            unsub = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, stop_motion_multicast
            )
            hass.data[DOMAIN][KEY_UNSUB_STOP] = unsub

    # Connect to motion gateway
    multicast = hass.data[DOMAIN][KEY_MULTICAST_LISTENER]
    connect_gateway_class = ConnectMotionGateway(hass, multicast)
    if not await connect_gateway_class.async_connect_gateway(host, key):
        raise ConfigEntryNotReady
    motion_gateway = connect_gateway_class.gateway_device
    api_lock = asyncio.Lock()
    coordinator_info = {
        KEY_GATEWAY: motion_gateway,
        KEY_API_LOCK: api_lock,
        CONF_WAIT_FOR_PUSH: wait_for_push,
    }

    coordinator = DataUpdateCoordinatorMotionBlinds(
        hass,
        _LOGGER,
        coordinator_info,
        # Name of the data. For logging purposes.
        name=entry.title,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    if motion_gateway.firmware is not None:
        version = f"{motion_gateway.firmware}, protocol: {motion_gateway.protocol}"
    else:
        version = f"Protocol: {motion_gateway.protocol}"

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_GATEWAY: motion_gateway,
        KEY_COORDINATOR: coordinator,
        KEY_VERSION: version,
    }

    if TYPE_CHECKING:
        assert entry.unique_id is not None

    if motion_gateway.device_type not in DEVICE_TYPES_WIFI:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, motion_gateway.mac)},
            identifiers={(DOMAIN, motion_gateway.mac)},
            manufacturer=MANUFACTURER,
            name=entry.title,
            model="Wi-Fi bridge",
            sw_version=version,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        multicast = hass.data[DOMAIN][KEY_MULTICAST_LISTENER]
        multicast.Unregister_motion_gateway(config_entry.data[CONF_HOST])
        hass.data[DOMAIN].pop(config_entry.entry_id)

    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        # No motion gateways left, stop Motion multicast
        unsub_stop = hass.data[DOMAIN].pop(KEY_UNSUB_STOP)
        unsub_stop()
        _LOGGER.debug("Shutting down Motion Listener")
        multicast = hass.data[DOMAIN].pop(KEY_MULTICAST_LISTENER)
        multicast.Stop_listen()

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
