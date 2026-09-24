"""Support for Broadlink devices."""

from collections.abc import Awaitable, Callable
from contextlib import suppress
import logging

import broadlink as blk
from broadlink.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BroadlinkException,
    ConnectionClosedError,
    EndpointClosedError,
    NetworkTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_PORT, DOMAIN, DOMAINS_AND_TYPES
from .updater import BroadlinkUpdateManager, get_update_manager

_LOGGER = logging.getLogger(__name__)


def get_domains(device_type: str) -> set[Platform]:
    """Return the domains available for a device type."""
    return {d for d, t in DOMAINS_AND_TYPES.items() if device_type in t}


class BroadlinkDevice[_ApiT: blk.Device = blk.Device]:
    """Manages a Broadlink device."""

    api: _ApiT

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config = config
        self.update_manager: BroadlinkUpdateManager[_ApiT] | None = None
        self.fw_version: int | None = None
        self.authorized: bool | None = None
        self.reset_jobs: list[CALLBACK_TYPE] = []

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.config.title

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the device."""
        return self.config.unique_id

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self.config.data[CONF_MAC]

    @property
    def available(self) -> bool | None:
        """Return True if the device is available."""
        if self.update_manager is None:
            return False
        return self.update_manager.available

    @staticmethod
    async def async_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Update the device and related entities.

        Triggered when the device is renamed on the frontend.
        """
        device_registry = dr.async_get(hass)
        assert entry.unique_id
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, entry.unique_id), entry.entry_id
        )
        assert device_entry
        device_registry.async_update_device(device_entry.id, name=entry.title)
        await hass.config_entries.async_reload(entry.entry_id)

    async def _async_get_firmware_version(self) -> int | None:
        """Get firmware version."""
        await self.api.auth()
        with suppress(BroadlinkException, OSError):
            return await self.api.get_fwversion()
        return None

    async def async_setup(self) -> bool:
        """Set up the device and related entities."""
        config = self.config

        api = blk.gendevice(
            config.data[CONF_TYPE],
            (config.data[CONF_HOST], DEFAULT_PORT),
            bytes.fromhex(config.data[CONF_MAC]),
            name=config.title,
        )
        api.timeout = config.data[CONF_TIMEOUT]
        self.api = api

        # The device is not registered yet, so a failure below must close
        # the endpoint auth() opened; async_unload will not run for it.
        try:
            self.fw_version = await self._async_get_firmware_version()

        except AuthenticationError:
            await api.aclose()
            await self._async_handle_auth_error()
            return False

        except (NetworkTimeoutError, OSError) as err:
            await api.aclose()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connect_failed",
                translation_placeholders={
                    "host": api.host[0],
                    "error": str(err),
                },
            ) from err

        except BroadlinkException as err:
            await api.aclose()
            _LOGGER.error(
                "Failed to authenticate to the device at %s: %s", api.host[0], err
            )
            return False

        self.authorized = True

        update_manager = get_update_manager(self)
        coordinator = update_manager.coordinator
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            await api.aclose()
            raise

        self.update_manager = update_manager
        # Uses legacy hass.data[DOMAIN] pattern
        # pylint: disable-next=home-assistant-use-runtime-data
        self.hass.data[DOMAIN].devices[config.entry_id] = self
        self.reset_jobs.append(config.add_update_listener(self.async_update))

        # Forward entry setup to related domains.
        await self.hass.config_entries.async_forward_entry_setups(
            config, get_domains(self.api.type)
        )

        return True

    async def async_unload(self) -> bool:
        """Unload the device and related entities."""
        if self.update_manager is None:
            return True

        while self.reset_jobs:
            self.reset_jobs.pop()()

        unloaded = await self.hass.config_entries.async_unload_platforms(
            self.config, get_domains(self.api.type)
        )
        if unloaded:
            await self.api.aclose()
        return unloaded

    async def async_auth(self) -> bool:
        """Authenticate to the device."""
        try:
            await self.api.auth()
        except (BroadlinkException, OSError) as err:
            _LOGGER.debug(
                "Failed to authenticate to the device at %s: %s", self.api.host[0], err
            )
            if isinstance(err, AuthenticationError):
                await self._async_handle_auth_error()
            return False
        return True

    async def async_request[**_P, _R](
        self,
        function: Callable[_P, Awaitable[_R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        """Send a request to the device.

        Re-authenticate and retry once on an authorization error; a request
        that fails because the endpoint was closed on unload is not retried.
        """
        try:
            return await function(*args, **kwargs)
        except EndpointClosedError:
            raise
        except AuthorizationError, ConnectionClosedError:
            if not await self.async_auth():
                raise
            return await function(*args, **kwargs)

    async def _async_handle_auth_error(self) -> None:
        """Handle an authentication error."""
        if self.authorized is False:
            return

        self.authorized = False

        _LOGGER.error(
            (
                "%s (%s at %s) is locked. Click Configuration in the sidebar, "
                "click Integrations, click Configure on the device and follow "
                "the instructions to unlock it"
            ),
            self.name,
            self.api.model,
            self.api.host[0],
        )

        self.config.async_start_reauth(self.hass, data={CONF_NAME: self.name})
