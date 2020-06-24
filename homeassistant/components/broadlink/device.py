"""Support for Broadlink devices."""
import asyncio
from functools import partial
import logging

import broadlink as blk
from broadlink.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BroadlinkException,
    ConnectionClosedError,
    DeviceOfflineError,
)

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_TIMEOUT, CONF_TYPE
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, DOMAINS_AND_TYPES
from .updater import get_update_coordinator

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80


class BroadlinkDevice:
    """Manages a Broadlink device."""

    def __init__(self, hass, config):
        """Initialize the device."""
        self.hass = hass
        self.config = config
        self.api = None
        self.coordinator = None
        self.fw_version = None
        self.authorized = None
        self.reset_jobs = []

    @property
    def name(self):
        """Return the name of the device."""
        return self.config.title

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self.config.unique_id

    @staticmethod
    async def async_update(hass, entry):
        """Update the device and related entities.

        Triggered when the device is renamed on the frontend.
        """
        # Update the name in the registry.
        device_registry = await dr.async_get_registry(hass)
        device_entry = device_registry.async_get_device(
            {(DOMAIN, entry.unique_id)}, set()
        )
        device_registry.async_update_device(device_entry.id, name=entry.title)

        # Update the name in the API and related entities.
        device = hass.data[DOMAIN].devices[entry.entry_id]
        device.api.name = entry.title
        await device.coordinator.async_request_refresh()

    async def async_setup(self):
        """Set up the device and related entities."""
        config = self.config
        name = config.title
        host = config.data[CONF_HOST]
        mac_addr = config.data[CONF_MAC]
        dev_type = config.data[CONF_TYPE]
        timeout = config.data[CONF_TIMEOUT]

        api = blk.gendevice(
            dev_type, (host, DEFAULT_PORT), bytes.fromhex(mac_addr), name=name
        )
        api.timeout = timeout

        try:
            await self.hass.async_add_executor_job(api.auth)

        except AuthenticationError:
            self.hass.async_create_task(self._async_handle_auth_error())
            return False

        except DeviceOfflineError:
            raise ConfigEntryNotReady

        self.api = api
        self.authorized = True

        coordinator = get_update_coordinator(self)
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            raise ConfigEntryNotReady()

        self.coordinator = coordinator
        self.hass.data[DOMAIN].devices[config.entry_id] = self
        self.reset_jobs.append(config.add_update_listener(self.async_update))

        try:
            self.fw_version = await self.hass.async_add_executor_job(api.get_fwversion)
        except BroadlinkException:
            self.fw_version = None

        # Forward entry setup to related domains.
        tasks = (
            self.hass.config_entries.async_forward_entry_setup(config, domain)
            for domain, types in DOMAINS_AND_TYPES
            if self.api.type in types
        )
        for entry_setup in tasks:
            self.hass.async_create_task(entry_setup)

        return True

    async def async_unload(self):
        """Unload the device and related entities."""
        if self.coordinator is None:
            return True

        while self.reset_jobs:
            self.reset_jobs.pop()()

        tasks = (
            self.hass.config_entries.async_forward_entry_unload(self.config, domain)
            for domain, types in DOMAINS_AND_TYPES
            if self.api.type in types
        )
        results = await asyncio.gather(*tasks)
        return False not in results

    async def async_auth(self):
        """Authenticate to the device."""
        try:
            await self.hass.async_add_executor_job(self.api.auth)
        except BroadlinkException as err:
            _LOGGER.debug(
                "Failed to authenticate to the device at %s: %s", self.api.host[0], err
            )
            if isinstance(err, AuthenticationError):
                self.hass.async_create_task(self._async_handle_auth_error())
            return False
        return True

    async def async_request(self, function, *args, **kwargs):
        """Send a request to the device."""
        request = partial(function, *args, **kwargs)
        try:
            return await self.hass.async_add_executor_job(request)
        except (AuthorizationError, ConnectionClosedError):
            if not await self.async_auth():
                raise
            return await self.hass.async_add_executor_job(request)

    async def _async_handle_auth_error(self):
        """Handle an authentication error."""
        if self.authorized is False:
            return

        self.authorized = False

        _LOGGER.error(
            "The device at %s is locked for authentication. Follow the configuration flow to unlock it",
            self.config.data[CONF_HOST],
        )
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "reauth"}, data=self.api,
            )
        )
