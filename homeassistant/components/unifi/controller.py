"""UniFi Controller abstraction."""
from datetime import timedelta

import asyncio
import ssl
import async_timeout

from aiohttp import CookieJar

import aiounifi

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_BLOCK_CLIENT,
    CONF_CONTROLLER,
    CONF_DETECTION_TIME,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONTROLLER_ID,
    DEFAULT_BLOCK_CLIENTS,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_DEVICES,
    DEFAULT_TRACK_WIRED_CLIENTS,
    DEFAULT_DETECTION_TIME,
    DEFAULT_SSID_FILTER,
    LOGGER,
    UNIFI_CONFIG,
)
from .errors import AuthenticationRequired, CannotConnect


class UniFiController:
    """Manages a single UniFi Controller."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None
        self.progress = None

        self._site_name = None
        self._site_role = None
        self.unifi_config = {}

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
    def event_update(self):
        """Event specific per UniFi entry to signal new data."""
        return "unifi-update-{}".format(
            CONTROLLER_ID.format(host=self.host, site=self.site)
        )

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

        async_dispatcher_send(self.hass, self.event_update)

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

        for unifi_config in hass.data[UNIFI_CONFIG]:
            if (
                self.host == unifi_config[CONF_HOST]
                and self.site_name == unifi_config[CONF_SITE_ID]
            ):
                self.unifi_config = unifi_config
                break

        options = dict(self.config_entry.options)

        if CONF_BLOCK_CLIENT in self.unifi_config:
            options[CONF_BLOCK_CLIENT] = self.unifi_config[CONF_BLOCK_CLIENT]

        if CONF_TRACK_CLIENTS in self.unifi_config:
            options[CONF_TRACK_CLIENTS] = self.unifi_config[CONF_TRACK_CLIENTS]

        if CONF_TRACK_DEVICES in self.unifi_config:
            options[CONF_TRACK_DEVICES] = self.unifi_config[CONF_TRACK_DEVICES]

        if CONF_TRACK_WIRED_CLIENTS in self.unifi_config:
            options[CONF_TRACK_WIRED_CLIENTS] = self.unifi_config[
                CONF_TRACK_WIRED_CLIENTS
            ]

        if CONF_DETECTION_TIME in self.unifi_config:
            options[CONF_DETECTION_TIME] = self.unifi_config[CONF_DETECTION_TIME]

        if CONF_SSID_FILTER in self.unifi_config:
            options[CONF_SSID_FILTER] = self.unifi_config[CONF_SSID_FILTER]

        hass.config_entries.async_update_entry(self.config_entry, options=options)

        for platform in ["device_tracker", "switch"]:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )

        return True

    async def async_reset(self):
        """Reset this controller to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        # If the authentication was wrong.
        if self.api is None:
            return True

        for platform in ["device_tracker", "switch"]:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, platform
            )

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
