"""Support for Broadlink IR/RF remotes."""
import asyncio
from base64 import b64encode
from binascii import hexlify
from collections import defaultdict
from datetime import timedelta
from ipaddress import ip_address
from itertools import product
import logging

import broadlink as blk
from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    DeviceOfflineError,
    ReadError,
)
import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DEFAULT_DELAY_SECS,
    DOMAIN as COMPONENT,
    PLATFORM_SCHEMA,
    SUPPORT_LEARN_COMMAND,
    RemoteEntity,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_TIMEOUT, CONF_TYPE
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from . import DOMAIN, data_packet, hostname, mac_address
from .const import (
    DEFAULT_LEARNING_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    RM4_TYPES,
    RM_TYPES,
)
from .device import BroadlinkDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=2)

CODE_STORAGE_VERSION = 1
FLAG_STORAGE_VERSION = 1
FLAG_SAVE_DELAY = 15

DEVICE_TYPES = RM_TYPES + RM4_TYPES

MINIMUM_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): vol.All(
            cv.ensure_list, [vol.All(cv.string, vol.Length(min=1))], vol.Length(min=1)
        ),
        vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_SCHEMA = MINIMUM_SERVICE_SCHEMA.extend(
    {vol.Optional(ATTR_DELAY_SECS, default=DEFAULT_DELAY_SECS): vol.Coerce(float)}
)

SERVICE_LEARN_SCHEMA = MINIMUM_SERVICE_SCHEMA.extend(
    {
        vol.Optional(ATTR_ALTERNATIVE, default=False): cv.boolean,
        vol.Optional(ATTR_TIMEOUT, default=DEFAULT_LEARNING_TIMEOUT): cv.positive_int,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): vol.All(vol.Any(hostname, ip_address), cv.string),
        vol.Required(CONF_MAC): mac_address,
        vol.Optional(CONF_TYPE, default=DEVICE_TYPES[0]): vol.In(DEVICE_TYPES),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Broadlink remote."""
    host = config[CONF_HOST]
    mac_addr = config[CONF_MAC]
    model = config[CONF_TYPE]
    timeout = config[CONF_TIMEOUT]
    name = config[CONF_NAME]
    unique_id = f"remote_{hexlify(mac_addr).decode('utf-8')}"

    if unique_id in hass.data.setdefault(DOMAIN, {}).setdefault(COMPONENT, []):
        _LOGGER.error("Duplicate: %s", unique_id)
        return
    hass.data[DOMAIN][COMPONENT].append(unique_id)

    if model in RM_TYPES:
        api = blk.rm((host, DEFAULT_PORT), mac_addr, None)
    else:
        api = blk.rm4((host, DEFAULT_PORT), mac_addr, None)
    api.timeout = timeout
    device = BroadlinkDevice(hass, api)

    code_storage = Store(hass, CODE_STORAGE_VERSION, f"broadlink_{unique_id}_codes")
    flag_storage = Store(hass, FLAG_STORAGE_VERSION, f"broadlink_{unique_id}_flags")

    remote = BroadlinkRemote(name, unique_id, device, code_storage, flag_storage)

    connected, loaded = await asyncio.gather(
        device.async_connect(), remote.async_load_storage_files()
    )
    if not connected:
        hass.data[DOMAIN][COMPONENT].remove(unique_id)
        raise PlatformNotReady
    if not loaded:
        _LOGGER.error("Failed to set up %s", unique_id)
        hass.data[DOMAIN][COMPONENT].remove(unique_id)
        return
    async_add_entities([remote], False)


class BroadlinkRemote(RemoteEntity):
    """Representation of a Broadlink remote."""

    def __init__(self, name, unique_id, device, code_storage, flag_storage):
        """Initialize the remote."""
        self.device = device
        self._name = name
        self._unique_id = unique_id
        self._code_storage = code_storage
        self._flag_storage = flag_storage
        self._codes = {}
        self._flags = defaultdict(int)
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
        return self.device.available

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LEARN_COMMAND

    @callback
    def get_flags(self):
        """Return dictionary of toggle flags.

        A toggle flag indicates whether `self._async_send_code()`
        should send an alternative code for a key device.
        """
        return self._flags

    async def async_turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = True

    async def async_turn_off(self, **kwargs):
        """Turn the remote off."""
        self._state = False

    async def async_update(self):
        """Update the availability of the device."""
        if not self.available:
            await self.device.async_connect()

    async def async_load_storage_files(self):
        """Load codes and toggle flags from storage files."""
        try:
            self._codes.update(await self._code_storage.async_load() or {})
            self._flags.update(await self._flag_storage.async_load() or {})
        except HomeAssistantError:
            return False
        return True

    async def async_send_command(self, command, **kwargs):
        """Send a list of commands to a device."""
        kwargs[ATTR_COMMAND] = command
        kwargs = SERVICE_SEND_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs[ATTR_DEVICE]
        repeat = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs[ATTR_DELAY_SECS]

        if not self._state:
            return

        should_delay = False
        for _, cmd in product(range(repeat), commands):
            try:
                should_delay = await self._async_send_code(
                    cmd, device, delay if should_delay else 0
                )
            except (AuthorizationError, DeviceOfflineError):
                break
            except BroadlinkException:
                pass

        self._flag_storage.async_delay_save(self.get_flags, FLAG_SAVE_DELAY)

    async def _async_send_code(self, command, device, delay):
        """Send a code to a device.

        For toggle commands, alternate between codes in a list,
        ensuring that the same code is never sent twice in a row.
        """
        try:
            code = self._codes[device][command]
        except KeyError:
            _LOGGER.error("Failed to send '%s/%s': Command not found", command, device)
            return False

        if isinstance(code, list):
            code = code[self._flags[device]]
            should_alternate = True
        else:
            should_alternate = False
        await asyncio.sleep(delay)

        try:
            await self.device.async_request(
                self.device.api.send_data, data_packet(code)
            )
        except ValueError:
            _LOGGER.error("Failed to send '%s/%s': Invalid code", command, device)
            return False
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to send '%s/%s': %s", command, device, err_msg)
            raise

        if should_alternate:
            self._flags[device] ^= 1

        return True

    async def async_learn_command(self, **kwargs):
        """Learn a list of commands from a remote."""
        kwargs = SERVICE_LEARN_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs[ATTR_DEVICE]
        toggle = kwargs[ATTR_ALTERNATIVE]
        timeout = kwargs[ATTR_TIMEOUT]

        if not self._state:
            return

        should_store = False
        for command in commands:
            try:
                should_store |= await self._async_learn_code(
                    command, device, toggle, timeout
                )
            except (AuthorizationError, DeviceOfflineError):
                break
            except BroadlinkException:
                pass

        if should_store:
            await self._code_storage.async_save(self._codes)

    async def _async_learn_code(self, command, device, toggle, timeout):
        """Learn a code from a remote.

        Capture an additional code for toggle commands.
        """
        try:
            if not toggle:
                code = await self._async_capture_code(command, timeout)
            else:
                code = [
                    await self._async_capture_code(command, timeout),
                    await self._async_capture_code(command, timeout),
                ]
        except TimeoutError:
            _LOGGER.error("Failed to learn '%s/%s': No code received", command, device)
            return False
        except BroadlinkException as err_msg:
            _LOGGER.error("Failed to learn '%s/%s': %s", command, device, err_msg)
            raise

        self._codes.setdefault(device, {}).update({command: code})
        return True

    async def _async_capture_code(self, command, timeout):
        """Enter learning mode and capture a code from a remote."""
        await self.device.async_request(self.device.api.enter_learning)

        self.hass.components.persistent_notification.async_create(
            f"Press the '{command}' button.",
            title="Learn command",
            notification_id="learn_command",
        )

        code = None
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=timeout):
            try:
                code = await self.device.async_request(self.device.api.check_data)
            except ReadError:
                await asyncio.sleep(1)
            else:
                break

        self.hass.components.persistent_notification.async_dismiss(
            notification_id="learn_command"
        )

        if code is None:
            raise TimeoutError

        return b64encode(code).decode("utf8")
