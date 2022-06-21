"""Support for Broadlink devices."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from contextlib import suppress
from functools import partial
import logging

import broadlink as blk
from broadlink.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BroadlinkException,
    ConnectionClosedError,
    NetworkTimeoutError,
)

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TIMEOUT, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store

from .const import DEFAULT_PORT, DOMAIN, DOMAINS_AND_TYPES
from .helpers import data_packet
from .updater import get_update_manager

CODE_SAVE_DELAY = 15
FLAG_SAVE_DELAY = 15

_LOGGER = logging.getLogger(__name__)


def get_domains(device_type):
    """Return the domains available for a device type."""
    return {d for d, t in DOMAINS_AND_TYPES.items() if device_type in t}


class BroadlinkStores:
    """Manages a storage setup for a device."""

    def __init__(self, codes_store: Store, flags_store: Store) -> None:
        """Initialize stores."""
        self._code_storage = codes_store
        self._flag_storage = flags_store
        self._codes: dict[str, dict[str, str | list[str]]] = {}
        self._flags: dict[str, int] = defaultdict(int)
        self._storage_loaded = False

    async def async_setup(self) -> None:
        """Load all stores and data."""
        self._codes.update(await self._code_storage.async_load() or {})
        self._flags.update(await self._flag_storage.async_load() or {})

    def extract_devices_and_commands(self) -> dict[str, list[str]]:
        """Return the set of devices and commands in storage."""
        return {device: list(subdevices) for device, subdevices in self._codes.items()}

    def extract_codes(
        self, commands: list[str], device: str | None = None
    ) -> list[list[bytes]]:
        """Extract a list of codes.

        If the command starts with `b64:`, extract the code from it.
        Otherwise, extract the code from storage, using the command and
        device as keys.

        The codes are returned in sublists. For toggle commands, the
        sublist contains two codes that must be sent alternately with
        each call.
        """

        def _data_packet_annotated(code):
            try:
                return data_packet(code)
            except ValueError as err:
                raise ValueError(f"Invalid code: {repr(code)}") from err

        code_list = []
        for cmd in commands:
            if cmd.startswith("b64:"):
                codes = [cmd[4:]]

            else:
                if device is None:
                    raise ValueError("You need to specify a device")

                try:
                    codes_raw = self._codes[device][cmd]
                except KeyError as err:
                    raise ValueError(f"Command not found: {repr(cmd)}") from err

                if isinstance(codes_raw, list):
                    codes = codes_raw[:]
                else:
                    codes = [codes_raw]

            data = [_data_packet_annotated(code) for code in codes]

            code_list.append(data)
        return code_list

    def toggled_codes(
        self, code_list: list[list[bytes]], subdevice: str | None = None
    ) -> Generator[bytes, None, None]:
        """Generate the list of codes we want and toggle as we go along."""
        try:
            for codes in code_list:
                if len(codes) > 1 and subdevice:
                    yield codes[self._flags[subdevice]]
                    self._flags[subdevice] ^= 1
                else:
                    yield codes[0]
        finally:
            self._flag_storage.async_delay_save(lambda: self._flags, FLAG_SAVE_DELAY)

    def add_commands(
        self, commands: dict[str, str | list[str]], subdevice: str
    ) -> None:
        """Add a set of commands."""
        self._codes.setdefault(subdevice, {}).update(commands)
        self._code_storage.async_delay_save(lambda: self._codes, CODE_SAVE_DELAY)

    def delete_commands(self, commands: list[str], subdevice: str) -> None:
        """Delete commands from a subdevice."""

        try:
            codes = self._codes[subdevice]
        except KeyError as err:
            err_msg = f"Device not found: {repr(subdevice)}"
            raise ValueError(err_msg) from err

        cmds_not_found = []
        for command in commands:
            try:
                del codes[command]
            except KeyError:
                cmds_not_found.append(command)

        if cmds_not_found:
            if len(cmds_not_found) == 1:
                err_msg = f"Command not found: {repr(cmds_not_found[0])}"
            else:
                err_msg = f"Commands not found: {repr(cmds_not_found)}"

            if len(cmds_not_found) == len(commands):
                raise ValueError(err_msg)

            _LOGGER.error("Error deleting: %s", err_msg)

        # Clean up
        if not codes:
            del self._codes[subdevice]
            if self._flags.pop(subdevice, None) is not None:
                self._flag_storage.async_delay_save(
                    lambda: self._flags, FLAG_SAVE_DELAY
                )

        self._code_storage.async_delay_save(lambda: self._codes, CODE_SAVE_DELAY)


class BroadlinkDevice:
    """Manages a Broadlink device."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, store: BroadlinkStores
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config = config
        self.api = None
        self.update_manager = None
        self.fw_version = None
        self.authorized = None
        self.reset_jobs: list[CALLBACK_TYPE] = []
        self.store = store

    @property
    def name(self):
        """Return the name of the device."""
        return self.config.title

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self.config.unique_id

    @property
    def mac_address(self):
        """Return the mac address of the device."""
        return self.config.data[CONF_MAC]

    @property
    def available(self):
        """Return True if the device is available."""
        if self.update_manager is None:  # pragma: no cover
            return False
        return self.update_manager.available

    @staticmethod
    async def async_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Update the device and related entities.

        Triggered when the device is renamed on the frontend.
        """
        device_registry = dr.async_get(hass)
        assert entry.unique_id
        device_entry = device_registry.async_get_device({(DOMAIN, entry.unique_id)})
        assert device_entry
        device_registry.async_update_device(device_entry.id, name=entry.title)
        await hass.config_entries.async_reload(entry.entry_id)

    def _get_firmware_version(self):
        """Get firmware version."""
        self.api.auth()
        with suppress(BroadlinkException, OSError):
            return self.api.get_fwversion()
        return None

    async def async_setup(self):
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

        try:
            self.fw_version = await self.hass.async_add_executor_job(
                self._get_firmware_version
            )

        except AuthenticationError:
            await self._async_handle_auth_error()
            return False

        except (NetworkTimeoutError, OSError) as err:
            raise ConfigEntryNotReady from err

        except BroadlinkException as err:
            _LOGGER.error(
                "Failed to authenticate to the device at %s: %s", api.host[0], err
            )
            return False

        self.authorized = True

        update_manager = get_update_manager(self)
        coordinator = update_manager.coordinator
        await coordinator.async_config_entry_first_refresh()

        self.update_manager = update_manager
        self.hass.data[DOMAIN].devices[config.entry_id] = self
        self.reset_jobs.append(config.add_update_listener(self.async_update))

        # Forward entry setup to related domains.
        await self.hass.config_entries.async_forward_entry_setups(
            config, get_domains(self.api.type)
        )

        return True

    async def async_unload(self):
        """Unload the device and related entities."""
        if self.update_manager is None:
            return True

        while self.reset_jobs:
            self.reset_jobs.pop()()

        return await self.hass.config_entries.async_unload_platforms(
            self.config, get_domains(self.api.type)
        )

    async def async_auth(self):
        """Authenticate to the device."""
        try:
            await self.hass.async_add_executor_job(self.api.auth)
        except (BroadlinkException, OSError) as err:
            _LOGGER.debug(
                "Failed to authenticate to the device at %s: %s", self.api.host[0], err
            )
            if isinstance(err, AuthenticationError):
                await self._async_handle_auth_error()
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
            "%s (%s at %s) is locked. Click Configuration in the sidebar, "
            "click Integrations, click Configure on the device and follow "
            "the instructions to unlock it",
            self.name,
            self.api.model,
            self.api.host[0],
        )

        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_REAUTH},
                data={CONF_NAME: self.name, **self.config.data},
            )
        )
