"""UniFi Controller abstraction."""
import asyncio
from datetime import timedelta
import ssl

from aiohttp import CookieJar
import aiounifi
import async_timeout

from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CONTROLLER,
    CONF_DETECTION_TIME,
    CONF_DONT_TRACK_CLIENTS,
    CONF_DONT_TRACK_DEVICES,
    CONF_DONT_TRACK_WIRED_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONTROLLER_ID,
    DEFAULT_ALLOW_BANDWIDTH_SENSORS,
    DEFAULT_BLOCK_CLIENTS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_SSID_FILTER,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_DEVICES,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DOMAIN,
    LOGGER,
    UNIFI_CONFIG,
    UNIFI_WIRELESS_CLIENTS,
)
from .errors import AuthenticationRequired, CannotConnect

SUPPORTED_PLATFORMS = ["device_tracker", "sensor", "switch"]


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
    def option_allow_bandwidth_sensors(self):
        """Config entry option to allow bandwidth sensors."""
        return self.config_entry.options.get(
            CONF_ALLOW_BANDWIDTH_SENSORS, DEFAULT_ALLOW_BANDWIDTH_SENSORS
        )

    @property
    def option_block_clients(self):
        """Config entry option with list of clients to control network access."""
        return self.config_entry.options.get(CONF_BLOCK_CLIENT, DEFAULT_BLOCK_CLIENTS)

    @property
    def option_track_clients(self):
        """Config entry option to not track clients."""
        return self.config_entry.options.get(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS)

    @property
    def option_track_devices(self):
        """Config entry option to not track devices."""
        return self.config_entry.options.get(CONF_TRACK_DEVICES, DEFAULT_TRACK_DEVICES)

    @property
    def option_track_wired_clients(self):
        """Config entry option to not track wired clients."""
        return self.config_entry.options.get(
            CONF_TRACK_WIRED_CLIENTS, DEFAULT_TRACK_WIRED_CLIENTS
        )

    @property
    def option_detection_time(self):
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    @property
    def option_ssid_filter(self):
        """Config entry option listing what SSIDs are being used to track clients."""
        return self.config_entry.options.get(CONF_SSID_FILTER, DEFAULT_SSID_FILTER)

    @property
    def mac(self):
        """Return the mac address of this controller."""
        for client in self.api.clients.values():
            if self.host == client.ip:
                return client.mac
        return None

    @property
    def signal_update(self):
        """Event specific per UniFi entry to signal new data."""
        return f"unifi-update-{CONTROLLER_ID.format(host=self.host, site=self.site)}"

    @property
    def signal_options_update(self):
        """Event specific per UniFi entry to signal new options."""
        return f"unifi-options-{CONTROLLER_ID.format(host=self.host, site=self.site)}"

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

    async def request_update(self):
        """Request an update."""
        if self.progress is not None:
            return await self.progress

        self.progress = self.hass.async_create_task(self.async_update())
        await self.progress

        self.progress = None

    async def async_update(self):
        """Update UniFi controller information."""
        failed = False

        try:
            with async_timeout.timeout(10):
                await self.api.clients.update()
                await self.api.devices.update()
                if self.option_block_clients:
                    await self.api.clients_all.update()

        except aiounifi.LoginRequired:
            try:
                with async_timeout.timeout(5):
                    await self.api.login()

            except (asyncio.TimeoutError, aiounifi.AiounifiException):
                failed = True
                if self.available:
                    LOGGER.error("Unable to reach controller %s", self.host)
                    self.available = False

        except (asyncio.TimeoutError, aiounifi.AiounifiException):
            failed = True
            if self.available:
                LOGGER.error("Unable to reach controller %s", self.host)
                self.available = False

        if not failed and not self.available:
            LOGGER.info("Reconnected to controller %s", self.host)
            self.available = True

        self.update_wireless_clients()

        async_dispatcher_send(self.hass, self.signal_update)

    async def async_setup(self):
        """Set up a UniFi controller."""
        hass = self.hass

        try:
            self.api = await get_controller(
                self.hass, **self.config_entry.data[CONF_CONTROLLER]
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

        wireless_clients = hass.data[UNIFI_WIRELESS_CLIENTS]
        self.wireless_clients = wireless_clients.get_data(self.config_entry)
        self.update_wireless_clients()

        self.import_configuration()

        self.config_entry.add_update_listener(self.async_options_updated)

        for platform in SUPPORTED_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )

        return True

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        controller_id = CONTROLLER_ID.format(
            host=entry.data[CONF_CONTROLLER][CONF_HOST],
            site=entry.data[CONF_CONTROLLER][CONF_SITE_ID],
        )
        controller = hass.data[DOMAIN][controller_id]

        async_dispatcher_send(hass, controller.signal_options_update)

    def import_configuration(self):
        """Import configuration to config entry options."""
        import_config = {}

        for config in self.hass.data[UNIFI_CONFIG]:
            if (
                self.host == config[CONF_HOST]
                and self.site_name == config[CONF_SITE_ID]
            ):
                import_config = config
                break

        old_options = dict(self.config_entry.options)
        new_options = {}

        for config, option in (
            (CONF_BLOCK_CLIENT, CONF_BLOCK_CLIENT),
            (CONF_DONT_TRACK_CLIENTS, CONF_TRACK_CLIENTS),
            (CONF_DONT_TRACK_WIRED_CLIENTS, CONF_TRACK_WIRED_CLIENTS),
            (CONF_DONT_TRACK_DEVICES, CONF_TRACK_DEVICES),
            (CONF_DETECTION_TIME, CONF_DETECTION_TIME),
            (CONF_SSID_FILTER, CONF_SSID_FILTER),
        ):
            if config in import_config:
                print(config)
                if config == option and import_config[
                    config
                ] != self.config_entry.options.get(option):
                    new_options[option] = import_config[config]
                elif config != option and (
                    option not in self.config_entry.options
                    or import_config[config] == self.config_entry.options.get(option)
                ):
                    new_options[option] = not import_config[config]

        if new_options:
            options = {**old_options, **new_options}
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    async def async_reset(self):
        """Reset this controller to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        for platform in SUPPORTED_PLATFORMS:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, platform
            )

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

        return True


async def get_controller(hass, host, username, password, port, site, verify_ssl):
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
    )

    try:
        with async_timeout.timeout(10):
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
