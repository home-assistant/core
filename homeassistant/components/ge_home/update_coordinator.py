"""Data update coordinator for GE Home Appliances"""

import asyncio
import async_timeout
import logging
from typing import Any, Dict, Iterable, Optional, Tuple

from gehomesdk import (
    EVENT_APPLIANCE_INITIAL_UPDATE,
    EVENT_APPLIANCE_UPDATE_RECEIVED,
    EVENT_CONNECTED,
    EVENT_DISCONNECTED,
    EVENT_GOT_APPLIANCE_LIST,
    ErdCodeType,
    GeAppliance,
    GeWebsocketClient,
)
from gehomesdk import GeAuthFailedError, GeGeneralServerError, GeNotAuthenticatedError
from .exceptions import HaAuthError, HaCannotConnect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    EVENT_ALL_APPLIANCES_READY,
    UPDATE_INTERVAL,
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    RETRY_OFFLINE_COUNT,
    ASYNC_TIMEOUT,
)
from .devices import ApplianceApi, get_appliance_api_type

PLATFORMS = ["binary_sensor", "sensor", "switch", "water_heater", "select", "climate", "light"]
_LOGGER = logging.getLogger(__name__)


class GeHomeUpdateCoordinator(DataUpdateCoordinator):
    """Define a wrapper class to update GE Home data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Set up the GeHomeUpdateCoordinator class."""
        self._hass = hass
        self._config_entry = config_entry
        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]
        self._appliance_apis = {}  # type: Dict[str, ApplianceApi]

        self._reset_initialization()

        super().__init__(hass, _LOGGER, name=DOMAIN)

    def _reset_initialization(self):
        self.client = None  # type: Optional[GeWebsocketClient]

        # Mark all appliances as not initialized yet
        for a in self.appliance_apis.values():
            a.appliance.initialized = False

        # Some record keeping to let us know when we can start generating entities
        self._got_roster = False
        self._init_done = False
        self._retry_count = 0
        self.initialization_future = asyncio.Future()

    def create_ge_client(
        self, event_loop: Optional[asyncio.AbstractEventLoop]
    ) -> GeWebsocketClient:
        """
        Create a new GeClient object with some helpful callbacks.

        :param event_loop: Event loop
        :return: GeWebsocketClient
        """
        client = GeWebsocketClient(
            self._username,
            self._password,
            event_loop=event_loop,
        )
        client.add_event_handler(EVENT_APPLIANCE_INITIAL_UPDATE, self.on_device_initial_update)
        client.add_event_handler(EVENT_APPLIANCE_UPDATE_RECEIVED, self.on_device_update)
        client.add_event_handler(EVENT_GOT_APPLIANCE_LIST, self.on_appliance_list)
        client.add_event_handler(EVENT_DISCONNECTED, self.on_disconnect)
        client.add_event_handler(EVENT_CONNECTED, self.on_connect)
        return client

    @property
    def appliances(self) -> Iterable[GeAppliance]:
        return self.client.appliances.values()

    @property
    def appliance_apis(self) -> Dict[str, ApplianceApi]:
        return self._appliance_apis

    @property
    def online(self) -> bool:
        """
        Indicates whether the services is online.  If it's retried several times, it's assumed
        that it's offline for some reason
        """
        return self.connected or self._retry_count <= RETRY_OFFLINE_COUNT

    @property
    def connected(self) -> bool:
        """
        Indicates whether the coordinator is connected
        """
        return self.client and self.client.connected

    def _get_appliance_api(self, appliance: GeAppliance) -> ApplianceApi:
        api_type = get_appliance_api_type(appliance.appliance_type)
        return api_type(self, appliance)

    def regenerate_appliance_apis(self):
        """Regenerate the appliance_apis dictionary, adding elements as necessary."""
        for jid, appliance in self.client.appliances.keys():
            if jid not in self._appliance_apis:
                self._appliance_apis[jid] = self._get_appliance_api(appliance)

    def maybe_add_appliance_api(self, appliance: GeAppliance):
        mac_addr = appliance.mac_addr
        if mac_addr not in self.appliance_apis:
            _LOGGER.debug(f"Adding appliance api for appliance {mac_addr} ({appliance.appliance_type})")
            api = self._get_appliance_api(appliance)
            api.build_entities_list()
            self.appliance_apis[mac_addr] = api
        else:
            # if we already have the API, switch out its appliance reference for this one
            api = self.appliance_apis[mac_addr]
            api.appliance = appliance

    async def get_client(self) -> GeWebsocketClient:
        """Get a new GE Websocket client."""
        if self.client:
            try:
                self.client.clear_event_handlers()
                await self.client.disconnect()
            except Exception as err:
                _LOGGER.warn(f"exception while disconnecting client {err}")
            finally:
                self._reset_initialization()

        loop = self._hass.loop
        self.client = self.create_ge_client(event_loop=loop)
        return self.client

    async def async_setup(self):
        """Setup a new coordinator"""
        _LOGGER.debug("Setting up coordinator")

        for component in PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self._config_entry, component
                )
            )

        try:
            await self.async_start_client()
        except (GeNotAuthenticatedError, GeAuthFailedError):
            raise HaAuthError("Authentication failure")
        except GeGeneralServerError:
            raise HaCannotConnect("Cannot connect (server error)")
        except Exception:
            raise HaCannotConnect("Unknown connection failure")

        try:
            with async_timeout.timeout(ASYNC_TIMEOUT):
                await self.initialization_future
        except (asyncio.CancelledError, asyncio.TimeoutError):
            raise HaCannotConnect("Initialization timed out")

        return True

    async def async_start_client(self):
        """Start a new GeClient in the HASS event loop."""
        try:
            _LOGGER.debug("Creating and starting client")
            await self.get_client()
            await self.async_begin_session()
        except:
            _LOGGER.debug("could not start the client")
            self.client = None
            raise

    async def async_begin_session(self):
        """Begins the ge_home session."""
        _LOGGER.debug("Beginning session")
        session = self._hass.helpers.aiohttp_client.async_get_clientsession()
        await self.client.async_get_credentials(session)
        fut = asyncio.ensure_future(self.client.async_run_client(), loop=self._hass.loop)
        _LOGGER.debug("Client running")
        return fut

    async def async_reset(self):
        """Resets the coordinator."""
        _LOGGER.debug("resetting the coordinator")
        entry = self._config_entry
        unload_ok = all(
            await asyncio.gather(
                *[
                    self.hass.config_entries.async_forward_entry_unload(
                        entry, component
                    )
                    for component in PLATFORMS
                ]
            )
        )
        return unload_ok

    async def _kill_client(self):
        """Kill the client.  Leaving this in for testing purposes."""
        await asyncio.sleep(30)
        _LOGGER.critical("Killing the connection.  Popcorn time.")
        await self.client.disconnect()

    @callback
    def reconnect(self, log=False) -> None:
        """Prepare to reconnect ge_home session."""
        if log:
            _LOGGER.info("Will try to reconnect to ge_home service")
        self.hass.loop.create_task(self.async_reconnect())

    async def async_reconnect(self) -> None:
        """Try to reconnect ge_home session."""
        self._retry_count += 1
        _LOGGER.info(
            f"attempting to reconnect to ge_home service (attempt {self._retry_count})"
        )

        try:
            with async_timeout.timeout(ASYNC_TIMEOUT):
                await self.async_start_client()
        except Exception as err:
            _LOGGER.warn(f"could not reconnect: {err}, will retry in {self._get_retry_delay()} seconds")
            self.hass.loop.call_later(self._get_retry_delay(), self.reconnect)
            _LOGGER.debug("forcing a state refresh while disconnected")
            try:
                await self._refresh_ha_state()
            except Exception as err:
                _LOGGER.debug(f"error refreshing state: {err}")

    @callback
    def shutdown(self, event) -> None:
        """Close the connection on shutdown.
        Used as an argument to EventBus.async_listen_once.
        """
        _LOGGER.info("ge_home shutting down")
        if self.client:
            self.client.clear_event_handlers()
            self.client.disconnect()

    async def on_device_update(self, data: Tuple[GeAppliance, Dict[ErdCodeType, Any]]):
        """Let HA know there's new state."""
        self.last_update_success = True
        appliance, _ = data
        try:
            api = self.appliance_apis[appliance.mac_addr]
        except KeyError:
            return
        for entity in api.entities:
            if entity.enabled:
                _LOGGER.debug(f"Updating {entity} ({entity.unique_id}, {entity.entity_id})")
                entity.async_write_ha_state()

    async def _refresh_ha_state(self):
        entities = [
            entity for api in self.appliance_apis.values() for entity in api.entities
        ]
        for entity in entities:
            if entity.enabled:
                try:
                    _LOGGER.debug(f"Refreshing state for {entity} ({entity.unique_id}, {entity.entity_id}")
                    entity.async_write_ha_state()
                except:
                    _LOGGER.debug(f"Could not refresh state for {entity} ({entity.unique_id}, {entity.entity_id}")

    @property
    def all_appliances_updated(self) -> bool:
        """True if all appliances have had an initial update."""
        return all([a.initialized for a in self.appliances])

    async def on_appliance_list(self, _):
        """When we get an appliance list, mark it and maybe trigger all ready."""
        _LOGGER.debug("Got roster update")
        self.last_update_success = True
        if not self._got_roster:
            self._got_roster = True
            # TODO: Probably should have a better way of confirming we're good to go...
            await asyncio.sleep(5)  
            # After the initial roster update, wait a bit and hit go
            await self.async_maybe_trigger_all_ready()

    async def on_device_initial_update(self, appliance: GeAppliance):
        """When an appliance first becomes ready, let the system know and schedule periodic updates."""
        _LOGGER.debug(f"Got initial update for {appliance.mac_addr}")
        self.last_update_success = True
        self.maybe_add_appliance_api(appliance)
        await self.async_maybe_trigger_all_ready()
        _LOGGER.debug(f"Requesting updates for {appliance.mac_addr}")
        while self.connected:
            await asyncio.sleep(UPDATE_INTERVAL)
            if self.connected and self.client.available:
                await appliance.async_request_update()

        _LOGGER.debug(f"No longer requesting updates for {appliance.mac_addr}")

    async def on_disconnect(self, _):
        """Handle disconnection."""
        _LOGGER.debug(f"Disconnected. Attempting to reconnect in {MIN_RETRY_DELAY} seconds")
        self.last_update_success = False
        self.hass.loop.call_later(MIN_RETRY_DELAY, self.reconnect, True)

    async def on_connect(self, _):
        """Set state upon connection."""
        self.last_update_success = True
        self._retry_count = 0

    async def async_maybe_trigger_all_ready(self):
        """See if we're all ready to go, and if so, let the games begin."""
        if self._init_done or self.initialization_future.done():
            # Been here, done this
            return
        if self._got_roster and self.all_appliances_updated:
            _LOGGER.debug("Ready to go.  Waiting 2 seconds and setting init future result.")
            # The the flag and wait to prevent two different fun race conditions
            self._init_done = True
            await asyncio.sleep(2)
            self.initialization_future.set_result(True)
            await self.client.async_event(EVENT_ALL_APPLIANCES_READY, None)

    def _get_retry_delay(self) -> int:
        delay = MIN_RETRY_DELAY * 2 ** (self._retry_count - 1)
        return min(delay, MAX_RETRY_DELAY)
