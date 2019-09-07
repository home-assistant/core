"""Support for Broadlink IR/RF remotes."""
import asyncio
from base64 import b64encode
from datetime import timedelta
from ipaddress import ip_address
from itertools import product, takewhile, zip_longest
import json
import logging
import socket

import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    DOMAIN as COMPONENT,
    PLATFORM_SCHEMA,
    SUPPORT_LEARN_COMMAND,
    RemoteDevice,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TIMEOUT
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

from . import DOMAIN, data_packet, hostname, mac_address

_LOGGER = logging.getLogger(__name__)

CONF_METADATA = ".metadata"

DEFAULT_LEARNING_TIMEOUT = 20
DEFAULT_NAME = "Broadlink"
DEFAULT_PORT = 80
DEFAULT_RETRY = 3
DEFAULT_TIMEOUT = 5

SCAN_INTERVAL = timedelta(minutes=2)

COMMAND_SCHEMA = vol.Schema(
    {
        vol.All(str, vol.Length(min=1)): {  # Device
            CONF_METADATA: dict,
            vol.All(str, vol.Length(min=1)): vol.Any(  # Command
                vol.All(str, vol.Length(min=1)),
                vol.All([vol.All(str, vol.Length(min=1))], vol.Length(min=2, max=2)),
            ),
        }
    }
)

TOGGLE_SCHEMA = vol.Schema({cv.string: vol.In([0, 1])})

MINIMUM_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): vol.All(
            cv.ensure_list,
            [vol.All(cv.string, vol.Length(min=1), vol.NotIn([CONF_METADATA]))],
            vol.Length(min=1),
        ),
        vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): vol.All(vol.Any(hostname, ip_address), cv.string),
        vol.Required(CONF_MAC): mac_address,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Broadlink remote."""
    import broadlink

    host = config.get(CONF_HOST)
    mac_addr = config.get(CONF_MAC).replace("-", "").lower()
    timeout = config.get(CONF_TIMEOUT)
    name = config.get(CONF_NAME)
    unique_id = f"remote_{mac_addr}"

    if mac_addr in hass.data.setdefault(DOMAIN, {}).setdefault(COMPONENT, []):
        _LOGGER.error("Duplicate remote: %s", config.get(CONF_MAC))
        return
    hass.data[DOMAIN][COMPONENT].append(mac_addr)

    api = broadlink.rm((host, DEFAULT_PORT), mac_addr, None)
    api.timeout = timeout
    remote = BroadlinkRemote(name, unique_id, api, hass.config.path)

    connected = False
    loaded = False
    try:
        connected, loaded = await asyncio.gather(
            hass.async_add_executor_job(api.auth), remote.async_retrieve_data()
        )
    except socket.error:
        pass
    if not connected:
        hass.data[DOMAIN][COMPONENT].remove(mac_addr)
        raise PlatformNotReady
    if not loaded:
        _LOGGER.error("Failed to set up remote: %s", config.get(CONF_MAC))
        hass.data[DOMAIN][COMPONENT].remove(mac_addr)
        return
    async_add_entities([remote], False)


class BroadlinkRemote(RemoteDevice):
    """Representation of a Broadlink remote."""

    def __init__(self, name, unique_id, api, config_path):
        """Initialize the remote."""
        self._name = name
        self._unique_id = unique_id
        self._api = api
        self._command_file = config_path(f"{unique_id}.json")
        self._toggle_file = config_path(f"{unique_id}.dat")
        self._commands = {}
        self._toggle = {}
        self._state = True
        self._available = True

    @property
    def name(self):
        """Return the name of the remote."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the remote."""
        return self._unique_id

    @property
    def is_on(self):
        """Return True if the remote is on."""
        return self._state

    @property
    def available(self):
        """Return True if the remote is available."""
        return self._available

    @property
    def should_poll(self):
        """Return True if the remote has to be polled for state."""
        return True

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LEARN_COMMAND

    async def async_turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = True

    async def async_turn_off(self, **kwargs):
        """Turn the remote off."""
        self._state = False

    async def async_update(self):
        """Update the availability of the remote."""
        if not self.available:
            await self._async_connect()

    async def async_send_command(self, command, **kwargs):
        """Send a list of commands to a device."""
        kwargs[ATTR_COMMAND] = command
        kwargs = MINIMUM_SERVICE_SCHEMA(kwargs)
        commands = kwargs.get(ATTR_COMMAND)
        device = kwargs.get(ATTR_DEVICE)
        repeat = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        if not self._state:
            return

        initial_toggle_value = self._toggle.get(device)

        should_delay = False
        for _, cmd in product(range(repeat), commands):
            try:
                should_delay = await self._async_send_single_command(
                    cmd, device, delay=delay if should_delay else 0
                )
            except ConnectionError:
                break

        if self._toggle.get(device) != initial_toggle_value:
            await self._async_store_toggle_data(self._toggle_file)

    async def _async_send_single_command(self, command, device, delay=0):
        """Send a single command to a device.

        For toggle commands, alternate between codes in a list,
        ensuring that the same code is never sent twice in a row.
        """
        try:
            code, is_toggle = (
                await asyncio.gather(
                    self._async_get_code(command, device), asyncio.sleep(delay)
                )
            )[0]
        except KeyError:
            _LOGGER.error("Failed to send '%s/%s': command not found", command, device)
            return False

        try:
            await self._async_attempt(self._api.send_data, data_packet(code))
        except ValueError:
            _LOGGER.error("Failed to send '%s/%s': invalid code", command, device)
            return False
        except ConnectionError:
            _LOGGER.error("Failed to send '%s/%s': remote is offline", command, device)
            raise

        if is_toggle:
            self._toggle[device] ^= 1
        return True

    async def _async_get_code(self, command, device):
        """Return the code and a toggle flag for a given command."""
        code = self._commands[device][command]
        if isinstance(code, list):
            return (code[self._toggle[device]], True)
        return (code, False)

    async def async_learn_command(self, **kwargs):
        """Learn a list of commands from a remote."""
        kwargs = MINIMUM_SERVICE_SCHEMA(kwargs)
        commands = kwargs.get(ATTR_COMMAND)
        device = kwargs.get(ATTR_DEVICE)
        toggle = kwargs.get(ATTR_ALTERNATIVE)
        timeout = kwargs.get(ATTR_TIMEOUT, DEFAULT_LEARNING_TIMEOUT)

        if not self._state:
            return

        should_store = False
        for command in commands:
            try:
                should_store |= await self._async_learn_single_command(
                    command, device, toggle=toggle, timeout=timeout
                )
            except ConnectionError:
                break

        if should_store:
            await self._async_store_commands(self._command_file)

    async def _async_learn_single_command(
        self, command, device, toggle=False, timeout=DEFAULT_LEARNING_TIMEOUT
    ):
        """Learn a single command from a remote."""
        try:
            code = await self._async_capture_code(
                command, toggle=toggle, timeout=timeout
            )
        except (ValueError, TimeoutError):
            _LOGGER.error(
                "Failed to learn '%s/%s': no signal received", command, device
            )
            return False
        except ConnectionError:
            _LOGGER.error("Failed to learn '%s/%s': remote is offline", command, device)
            raise

        try:
            self._commands[device][command] = code
        except KeyError:  # New device
            self._commands[device] = {command: code}
            self._toggle[device] = 0
        return True

    async def _async_capture_code(
        self, command, toggle=False, timeout=DEFAULT_LEARNING_TIMEOUT
    ):
        """Enter learning mode and capture a code from a remote.

        Capture an aditional code for toggle commands.
        """
        await self._async_attempt(self._api.enter_learning)

        self.hass.components.persistent_notification.async_create(
            f"Press the '{command}' button.",
            title="Learn command",
            notification_id="learn_command",
        )

        code = None
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=timeout):
            code = await self.hass.async_add_executor_job(self._api.check_data)
            if code:
                break
            await asyncio.sleep(1)

        self.hass.components.persistent_notification.async_dismiss(
            notification_id="learn_command"
        )

        if not code:
            raise TimeoutError
        if all(not value for value in code):
            raise ValueError

        code = b64encode(code).decode("utf8")
        return (
            code
            if not toggle
            else [code, await self._async_capture_code(command, timeout=timeout)]
        )

    async def _async_attempt(self, function, *args):
        """Retry a socket-related function until it succeeds."""
        for retry in range(DEFAULT_RETRY):
            if retry and not await self._async_connect():
                continue
            try:
                await self.hass.async_add_executor_job(function, *args)
            except socket.error:
                continue
            return
        raise ConnectionError

    async def _async_connect(self):
        """Connect to the remote."""
        try:
            auth = await self.hass.async_add_executor_job(self._api.auth)
        except socket.error:
            auth = False
        if auth and not self._available:
            _LOGGER.warning("Connected to the remote")
            self._available = True
        elif not auth and self._available:
            _LOGGER.warning("Disconnected from the remote")
            self._available = False
        return auth

    async def async_retrieve_data(self):
        """Load dictionary of commands and toggle data from files."""
        try:
            await self._async_load_commands(self._command_file)
            await self._async_load_toggle_data(self._toggle_file)
        except FileNotFoundError:
            pass  # No problem. The file will be created soon.
        except (IOError, json.JSONDecodeError, vol.MultipleInvalid):
            return False
        return True

    async def _async_load_commands(self, file_path):
        """Load dictionary of commands from a JSON file."""
        try:
            with open(file_path, "r") as json_file:
                self._commands = COMMAND_SCHEMA(json.load(json_file))
        except FileNotFoundError:
            raise
        except IOError as err:
            _LOGGER.error("Failed to load '%s': %s", file_path, err.strerror)
            raise
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to load '%s': %s", file_path, err)
            raise
        except vol.MultipleInvalid as err:
            _LOGGER.error("Failed to load '%s': %s", file_path, err)
            raise

    async def _async_store_commands(self, file_path):
        """Dump dictionary of commands into a JSON file."""
        try:
            with open(file_path, "w") as json_file:
                json.dump(self._commands, json_file, indent=4)
        except IOError as err:
            _LOGGER.error("Failed to write '%s': %s", file_path, err.strerror)

    async def _async_load_toggle_data(self, file_path):
        """Load dictionary of toggle values from a binary file.

        You should call ``self._async_load_commands()`` first.
        """
        try:
            with open(file_path, "rb") as bin_file:
                self._toggle = TOGGLE_SCHEMA(
                    dict(
                        takewhile(
                            lambda d: d[0],
                            zip_longest(self._commands, bin_file.read(), fillvalue=0),
                        )
                    )
                )
        except FileNotFoundError:
            raise
        except IOError as err:
            _LOGGER.error("Failed to load '%s': %s", file_path, err.strerror)
            raise
        except vol.MultipleInvalid as err:
            _LOGGER.error("Failed to load '%s': %s", file_path, err)
            raise

    async def _async_store_toggle_data(self, file_path):
        """Store dictionary of toggle values into a binary file."""
        try:
            with open(file_path, "wb") as bin_file:
                bin_file.write(bytes(self._toggle.values()))
        except IOError as err:
            _LOGGER.error("Failed to write '%s': %s", file_path, err.strerror)
