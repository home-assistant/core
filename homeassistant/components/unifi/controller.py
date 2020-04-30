"""UniFi Controller abstraction."""
import asyncio
from datetime import timedelta
import ssl

from aiohttp import CookieJar
import aiounifi
from aiounifi.controller import (
    DATA_CLIENT,
    DATA_CLIENT_REMOVED,
    DATA_DEVICE,
    DATA_EVENT,
    SIGNAL_CONNECTION_STATE,
    SIGNAL_DATA,
)
from aiounifi.events import WIRELESS_CLIENT_CONNECTED, WIRELESS_GUEST_CONNECTED
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING
import async_timeout

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CONTROLLER,
    CONF_DETECTION_TIME,
    CONF_IGNORE_WIRED_BUG,
    CONF_POE_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONTROLLER_ID,
    DEFAULT_ALLOW_BANDWIDTH_SENSORS,
    DEFAULT_DETECTION_TIME,
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
SUPPORTED_PLATFORMS = [TRACKER_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]


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

        self.listeners = []
        self._site_name = None
        self._site_role = None

        self.entities = {}

    @property
    def controller_id(self):
        """Return the controller ID."""
        return CONTROLLER_ID.format(host=self.host, site=self.site)

    @property
    def host(self):
        """Return the host of this controller."""
        return self.config_entry.data[CONF_CONTROLLER][CONF_HOST]

    @property
    def site(self):
        """Return the site of this config entry."""
        return self.config_entry.data[CONF_CONTROLLER][CONF_SITE_ID]

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

    # Device tracker options

    @property
    def option_track_clients(self):
        """Config entry option to not track clients."""
        return self.config_entry.options.get(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS)

    @property
    def option_track_wired_clients(self):
        """Config entry option to not track wired clients."""
        return self.config_entry.options.get(
            CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
        )

    @property
    def option_track_devices(self):
        """Config entry option to not track devices."""
        return self.config_entry.options.get(CONF_TRACK_DEVICES, DEFAULT_TRACK_DEVICES)

    @property
    def option_ssid_filter(self):
        """Config entry option listing what SSIDs are being used to track clients."""
        return self.config_entry.options.get(CONF_SSID_FILTER, [])

    @property
    def option_detection_time(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    @property
    def option_ignore_wired_bug(self):
        """Config entry option to ignore wired bug."""
        return self.config_entry.options.get(
            CONF_IGNORE_WIRED_BUG, DEFAULT_IGNORE_WIRED_BUG
        )

    # Client control options

    @property
    def option_poe_clients(self):
        """Config entry option to control poe clients."""
        return self.config_entry.options.get(CONF_POE_CLIENTS, DEFAULT_POE_CLIENTS)

    @property
    def option_block_clients(self):
        """Config entry option with list of clients to control network access."""
        return self.config_entry.options.get(CONF_BLOCK_CLIENT, [])

    # Statistics sensor options

    @property
    def option_allow_bandwidth_sensors(self):
        """Config entry option to allow bandwidth sensors."""
        return self.config_entry.options.get(
            CONF_ALLOW_BANDWIDTH_SENSORS, DEFAULT_ALLOW_BANDWIDTH_SENSORS
        )

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
                if data[DATA_EVENT].event in (
                    WIRELESS_CLIENT_CONNECTED,
                    WIRELESS_GUEST_CONNECTED,
                ):
                    self.update_wireless_clients()

            elif DATA_CLIENT in data or DATA_DEVICE in data:
                async_dispatcher_send(self.hass, self.signal_update)

            elif DATA_CLIENT_REMOVED in data:
                async_dispatcher_send(
                    self.hass, self.signal_remove, data[DATA_CLIENT_REMOVED]
                )

    @property
    def signal_reachable(self) -> str:
        """Integration specific event to signal a change in connection status."""
        return f"unifi-reachable-{self.controller_id}"

    @property
    def signal_update(self):
        """Event specific per UniFi entry to signal new data."""
        return f"unifi-update-{self.controller_id}"

    @property
    def signal_remove(self):
        """Event specific per UniFi entry to signal removal of entities."""
        return f"unifi-remove-{self.controller_id}"

    @property
    def signal_options_update(self):
        """Event specific per UniFi entry to signal new options."""
        return f"unifi-options-{self.controller_id}"

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
                **self.config_entry.data[CONF_CONTROLLER],
                async_callback=self.async_unifi_signalling_callback,
            )
            await self.api.initialize()

            sites = await self.api.sites()

            for site in sites.values():
                if self.site == site["name"]:
                    self._site_name = site["desc"]
                    self._site_role = site["role"]
                    break

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Unknown error connecting with UniFi controller: %s", err)
            return False

        # Restore clients that is not a part of active clients list.
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        for entity in entity_registry.entities.values():
            if (
                entity.config_entry_id != self.config_entry.entry_id
                or "-" not in entity.unique_id
            ):
                continue

            mac = ""
            if entity.domain == TRACKER_DOMAIN:
                mac, _ = entity.unique_id.split("-", 1)
            elif entity.domain == SWITCH_DOMAIN:
                _, mac = entity.unique_id.split("-", 1)

            if mac in self.api.clients or mac not in self.api.clients_all:
                continue

            client = self.api.clients_all[mac]
            self.api.clients.process_raw([client.raw])
            LOGGER.debug(
                "Restore disconnected client %s (%s)", entity.entity_id, client.mac,
            )

        wireless_clients = self.hass.data[UNIFI_WIRELESS_CLIENTS]
        self.wireless_clients = wireless_clients.get_data(self.config_entry)
        self.update_wireless_clients()

        for platform in SUPPORTED_PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )

        self.api.start_websocket()

        self.config_entry.add_update_listener(self.async_config_entry_updated)

        return True

    @staticmethod
    async def async_config_entry_updated(hass, config_entry) -> None:
        """Handle signals of config entry being updated."""
        controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
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

        except (asyncio.TimeoutError, aiounifi.AiounifiException):
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

        for platform in SUPPORTED_PLATFORMS:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, platform
            )

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

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

    except aiounifi.Unauthorized:
        LOGGER.warning("Connected to UniFi at %s but not registered.", host)
        raise AuthenticationRequired

    except (asyncio.TimeoutError, aiounifi.RequestError):
        LOGGER.error("Error connecting to the UniFi controller at %s", host)
        raise CannotConnect

    except aiounifi.AiounifiException:
        LOGGER.exception("Unknown UniFi communication error occurred")
        raise AuthenticationRequired
