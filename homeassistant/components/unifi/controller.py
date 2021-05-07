"""UniFi Controller abstraction."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import ssl

from aiohttp import CookieJar
import aiounifi
from aiounifi.controller import (
    DATA_CLIENT_REMOVED,
    DATA_DPI_GROUP,
    DATA_DPI_GROUP_REMOVED,
    DATA_EVENT,
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
)
from aiounifi.events import (
    ACCESS_POINT_CONNECTED,
    GATEWAY_CONNECTED,
    SWITCH_CONNECTED,
    WIRED_CLIENT_CONNECTED,
    WIRELESS_CLIENT_CONNECTED,
    WIRELESS_GUEST_CONNECTED,
)
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING
import async_timeout

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.switch import BLOCK_SWITCH, POE_SWITCH
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_POE_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DEFAULT_ALLOW_BANDWIDTH_SENSORS,
    DEFAULT_ALLOW_UPTIME_SENSORS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_DPI_RESTRICTIONS,
    DEFAULT_IGNORE_WIRED_BUG,
    DEFAULT_POE_CLIENTS,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_DEVICES,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
    LOGGER,
    UNIFI_WIRELESS_CLIENTS,
)
from .errors import AuthenticationRequired, CannotConnect

RETRY_TIMER = 15
CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)
PLATFORMS = [TRACKER_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]

CLIENT_CONNECTED = (
    WIRED_CLIENT_CONNECTED,
    WIRELESS_CLIENT_CONNECTED,
    WIRELESS_GUEST_CONNECTED,
)
DEVICE_CONNECTED = (
    ACCESS_POINT_CONNECTED,
    GATEWAY_CONNECTED,
    SWITCH_CONNECTED,
)


class UniFiController:
    """Manages a single UniFi Controller."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None
        self.progress = None
        self.wireless_clients = None

        self.site_id: str = ""
        self._site_name = None
        self._site_role = None

        self._cancel_heartbeat_check = None
        self._heartbeat_dispatch = {}
        self._heartbeat_time = {}

        self.load_config_entry_options()

        self.entities = {}

    def load_config_entry_options(self):
        """Store attributes to avoid property call overhead since they are called frequently."""
        options = self.config_entry.options

        # Device tracker options

        # Config entry option to not track clients.
        self.option_track_clients = options.get(
            CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS
        )
        # Config entry option to not track wired clients.
        self.option_track_wired_clients = options.get(
            CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
        )
        # Config entry option to not track devices.
        self.option_track_devices = options.get(
            CONF_TRACK_DEVICES, DEFAULT_TRACK_DEVICES
        )
        # Config entry option listing what SSIDs are being used to track clients.
        self.option_ssid_filter = set(options.get(CONF_SSID_FILTER, []))
        # Config entry option defining number of seconds from last seen to away
        self.option_detection_time = timedelta(
            seconds=options.get(CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME)
        )
        # Config entry option to ignore wired bug.
        self.option_ignore_wired_bug = options.get(
            CONF_IGNORE_WIRED_BUG, DEFAULT_IGNORE_WIRED_BUG
        )

        # Client control options

        # Config entry option to control poe clients.
        self.option_poe_clients = options.get(CONF_POE_CLIENTS, DEFAULT_POE_CLIENTS)
        # Config entry option with list of clients to control network access.
        self.option_block_clients = options.get(CONF_BLOCK_CLIENT, [])
        # Config entry option to control DPI restriction groups.
        self.option_dpi_restrictions = options.get(
            CONF_DPI_RESTRICTIONS, DEFAULT_DPI_RESTRICTIONS
        )

        # Statistics sensor options

        # Config entry option to allow bandwidth sensors.
        self.option_allow_bandwidth_sensors = options.get(
            CONF_ALLOW_BANDWIDTH_SENSORS, DEFAULT_ALLOW_BANDWIDTH_SENSORS
        )
        # Config entry option to allow uptime sensors.
        self.option_allow_uptime_sensors = options.get(
            CONF_ALLOW_UPTIME_SENSORS, DEFAULT_ALLOW_UPTIME_SENSORS
        )

    @property
    def host(self):
        """Return the host of this controller."""
        return self.config_entry.data[CONF_HOST]

    @property
    def site(self):
        """Return the site of this config entry."""
        return self.config_entry.data[CONF_SITE_ID]

    @property
    def site_name(self):
        """Return the nice name of site."""
        return self._site_name

    @property
    def site_role(self):
        """Return the site user role of this controller."""
        return self._site_role

    @property
    def mac(self):
        """Return the mac address of this controller."""
        for client in self.api.clients.values():
            if self.host == client.ip:
                return client.mac
        return None

    @callback
    def async_unifi_signalling_callback(self, signal, data):
        """Handle messages back from UniFi library."""
        if signal == SIGNAL_CONNECTION_STATE:

            if data == STATE_DISCONNECTED and self.available:
                LOGGER.warning("Lost connection to UniFi controller")

            if (data == STATE_RUNNING and not self.available) or (
                data == STATE_DISCONNECTED and self.available
            ):
                self.available = data == STATE_RUNNING
                async_dispatcher_send(self.hass, self.signal_reachable)

                if not self.available:
                    self.hass.loop.call_later(RETRY_TIMER, self.reconnect, True)
                else:
                    LOGGER.info("Connected to UniFi controller")

        elif signal == SIGNAL_DATA and data:

            if DATA_EVENT in data:
                clients_connected = set()
                devices_connected = set()
                wireless_clients_connected = False

                for event in data[DATA_EVENT]:

                    if event.event in CLIENT_CONNECTED:
                        clients_connected.add(event.mac)

                        if not wireless_clients_connected and event.event in (
                            WIRELESS_CLIENT_CONNECTED,
                            WIRELESS_GUEST_CONNECTED,
                        ):
                            wireless_clients_connected = True

                    elif event.event in DEVICE_CONNECTED:
                        devices_connected.add(event.mac)

                if wireless_clients_connected:
                    self.update_wireless_clients()
                if clients_connected or devices_connected:
                    async_dispatcher_send(
                        self.hass,
                        self.signal_update,
                        clients_connected,
                        devices_connected,
                    )

            elif DATA_CLIENT_REMOVED in data:
                async_dispatcher_send(
                    self.hass, self.signal_remove, data[DATA_CLIENT_REMOVED]
                )

            elif DATA_DPI_GROUP in data:
                for key in data[DATA_DPI_GROUP]:
                    if self.api.dpi_groups[key].dpiapp_ids:
                        async_dispatcher_send(self.hass, self.signal_update)
                    else:
                        async_dispatcher_send(self.hass, self.signal_remove, {key})

            elif DATA_DPI_GROUP_REMOVED in data:
                async_dispatcher_send(
                    self.hass, self.signal_remove, data[DATA_DPI_GROUP_REMOVED]
                )

    @property
    def signal_reachable(self) -> str:
        """Integration specific event to signal a change in connection status."""
        return f"unifi-reachable-{self.config_entry.entry_id}"

    @property
    def signal_update(self) -> str:
        """Event specific per UniFi entry to signal new data."""
        return f"unifi-update-{self.config_entry.entry_id}"

    @property
    def signal_remove(self) -> str:
        """Event specific per UniFi entry to signal removal of entities."""
        return f"unifi-remove-{self.config_entry.entry_id}"

    @property
    def signal_options_update(self) -> str:
        """Event specific per UniFi entry to signal new options."""
        return f"unifi-options-{self.config_entry.entry_id}"

    @property
    def signal_heartbeat_missed(self) -> str:
        """Event specific per UniFi device tracker to signal new heartbeat missed."""
        return "unifi-heartbeat-missed"

    def update_wireless_clients(self):
        """Update set of known to be wireless clients."""
        new_wireless_clients = set()

        for client_id in self.api.clients:
            if (
                client_id not in self.wireless_clients
                and not self.api.clients[client_id].is_wired
            ):
                new_wireless_clients.add(client_id)

        if new_wireless_clients:
            self.wireless_clients |= new_wireless_clients
            unifi_wireless_clients = self.hass.data[UNIFI_WIRELESS_CLIENTS]
            unifi_wireless_clients.update_data(self.wireless_clients, self.config_entry)

    async def async_setup(self):
        """Set up a UniFi controller."""
        try:
            self.api = await get_controller(
                self.hass,
                host=self.config_entry.data[CONF_HOST],
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                port=self.config_entry.data[CONF_PORT],
                site=self.config_entry.data[CONF_SITE_ID],
                verify_ssl=self.config_entry.data[CONF_VERIFY_SSL],
                async_callback=self.async_unifi_signalling_callback,
            )
            await self.api.initialize()

            sites = await self.api.sites()
            description = await self.api.site_description()

        except CannotConnect as err:
            raise ConfigEntryNotReady from err

        except AuthenticationRequired as err:
            raise ConfigEntryAuthFailed from err

        for site in sites.values():
            if self.site == site["name"]:
                self.site_id = site["_id"]
                self._site_name = site["desc"]
                break

        self._site_role = description[0]["site_role"]

        # Restore clients that are not a part of active clients list.
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        for entry in async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        ):
            if entry.domain == TRACKER_DOMAIN:
                mac = entry.unique_id.split("-", 1)[0]
            elif entry.domain == SWITCH_DOMAIN and (
                entry.unique_id.startswith(BLOCK_SWITCH)
                or entry.unique_id.startswith(POE_SWITCH)
            ):
                mac = entry.unique_id.split("-", 1)[1]
            else:
                continue

            if mac in self.api.clients or mac not in self.api.clients_all:
                continue

            client = self.api.clients_all[mac]
            self.api.clients.process_raw([client.raw])
            LOGGER.debug(
                "Restore disconnected client %s (%s)",
                entry.entity_id,
                client.mac,
            )

        wireless_clients = self.hass.data[UNIFI_WIRELESS_CLIENTS]
        self.wireless_clients = wireless_clients.get_data(self.config_entry)
        self.update_wireless_clients()

        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

        self.api.start_websocket()

        self.config_entry.add_update_listener(self.async_config_entry_updated)

        self._cancel_heartbeat_check = async_track_time_interval(
            self.hass, self._async_check_for_stale, CHECK_HEARTBEAT_INTERVAL
        )

        return True

    @callback
    def async_heartbeat(
        self, unique_id: str, heartbeat_expire_time: datetime | None = None
    ) -> None:
        """Signal when a device has fresh home state."""
        if heartbeat_expire_time is not None:
            self._heartbeat_time[unique_id] = heartbeat_expire_time
            return

        if unique_id in self._heartbeat_time:
            del self._heartbeat_time[unique_id]

    @callback
    def _async_check_for_stale(self, *_) -> None:
        """Check for any devices scheduled to be marked disconnected."""
        now = dt_util.utcnow()

        for unique_id, heartbeat_expire_time in self._heartbeat_time.items():
            if now > heartbeat_expire_time:
                async_dispatcher_send(
                    self.hass, f"{self.signal_heartbeat_missed}_{unique_id}"
                )

    @staticmethod
    async def async_config_entry_updated(hass, config_entry) -> None:
        """Handle signals of config entry being updated.

        If config entry is updated due to reauth flow
        the entry might already have been reset and thus is not available.
        """
        if not (controller := hass.data[UNIFI_DOMAIN].get(config_entry.entry_id)):
            return
        controller.load_config_entry_options()
        async_dispatcher_send(hass, controller.signal_options_update)

    @callback
    def reconnect(self, log=False) -> None:
        """Prepare to reconnect UniFi session."""
        if log:
            LOGGER.info("Will try to reconnect to UniFi controller")
        self.hass.loop.create_task(self.async_reconnect())

    async def async_reconnect(self) -> None:
        """Try to reconnect UniFi session."""
        try:
            with async_timeout.timeout(5):
                await self.api.login()
                self.api.start_websocket()

        except (
            asyncio.TimeoutError,
            aiounifi.BadGateway,
            aiounifi.ServiceUnavailable,
            aiounifi.AiounifiException,
        ):
            self.hass.loop.call_later(RETRY_TIMER, self.reconnect)

    @callback
    def shutdown(self, event) -> None:
        """Wrap the call to unifi.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.stop_websocket()

    async def async_reset(self):
        """Reset this controller to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        self.api.stop_websocket()

        unload_ok = await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

        if not unload_ok:
            return False

        if self._cancel_heartbeat_check:
            self._cancel_heartbeat_check()
            self._cancel_heartbeat_check = None

        return True


async def get_controller(
    hass, host, username, password, port, site, verify_ssl, async_callback=None
):
    """Create a controller object and verify authentication."""
    sslcontext = None

    if verify_ssl:
        session = aiohttp_client.async_get_clientsession(hass)
        if isinstance(verify_ssl, str):
            sslcontext = ssl.create_default_context(cafile=verify_ssl)
    else:
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=verify_ssl, cookie_jar=CookieJar(unsafe=True)
        )

    controller = aiounifi.Controller(
        host,
        username=username,
        password=password,
        port=port,
        site=site,
        websession=session,
        sslcontext=sslcontext,
        callback=async_callback,
    )

    try:
        with async_timeout.timeout(10):
            await controller.check_unifi_os()
            await controller.login()
        return controller

    except aiounifi.Unauthorized as err:
        LOGGER.warning("Connected to UniFi at %s but not registered: %s", host, err)
        raise AuthenticationRequired from err

    except (
        asyncio.TimeoutError,
        aiounifi.BadGateway,
        aiounifi.ServiceUnavailable,
        aiounifi.RequestError,
    ) as err:
        LOGGER.error("Error connecting to the UniFi controller at %s: %s", host, err)
        raise CannotConnect from err

    except aiounifi.LoginRequired as err:
        LOGGER.warning("Connected to UniFi at %s but login required: %s", host, err)
        raise AuthenticationRequired from err

    except aiounifi.AiounifiException as err:
        LOGGER.exception("Unknown UniFi communication error occurred: %s", err)
        raise AuthenticationRequired from err
