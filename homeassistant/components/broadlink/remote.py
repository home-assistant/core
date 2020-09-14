"""Support for Broadlink remotes."""
import asyncio
from base64 import b64encode
from collections import defaultdict
from datetime import timedelta
from itertools import product
import logging

from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    DeviceOfflineError,
    ReadError,
    StorageError,
)
import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    PLATFORM_SCHEMA,
    SUPPORT_LEARN_COMMAND,
    RemoteEntity,
)
from homeassistant.const import CONF_HOST, STATE_ON
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .helpers import data_packet, import_device

_LOGGER = logging.getLogger(__name__)

LEARNING_TIMEOUT = timedelta(seconds=30)

CODE_STORAGE_VERSION = 1
FLAG_STORAGE_VERSION = 1
FLAG_SAVE_DELAY = 15

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): vol.All(
            cv.ensure_list, [vol.All(cv.string, vol.Length(min=1))], vol.Length(min=1)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Optional(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_DELAY_SECS, default=DEFAULT_DELAY_SECS): vol.Coerce(float),
    }
)

SERVICE_LEARN_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_ALTERNATIVE, default=False): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string}, extra=vol.ALLOW_EXTRA
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the device and discontinue platform.

    This is for backward compatibility.
    Do not use this method.
    """
    import_device(hass, config[CONF_HOST])
    _LOGGER.warning(
        "The remote platform is deprecated, please remove it from your configuration"
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Broadlink remote."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    remote = BroadlinkRemote(
        device,
        Store(hass, CODE_STORAGE_VERSION, f"broadlink_remote_{device.unique_id}_codes"),
        Store(hass, FLAG_STORAGE_VERSION, f"broadlink_remote_{device.unique_id}_flags"),
    )

    loaded = await remote.async_load_storage_files()
    if not loaded:
        _LOGGER.error("Failed to create '%s Remote' entity: Storage error", device.name)
        return

    async_add_entities([remote], False)


class BroadlinkRemote(RemoteEntity, RestoreEntity):
    """Representation of a Broadlink remote."""

    def __init__(self, device, codes, flags):
        """Initialize the remote."""
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._code_storage = codes
        self._flag_storage = flags
        self._codes = {}
        self._flags = defaultdict(int)
        self._state = True

    @property
    def name(self):
        """Return the name of the remote."""
        return f"{self._device.name} Remote"

    @property
    def unique_id(self):
        """Return the unique id of the remote."""
        return self._device.unique_id

    @property
    def is_on(self):
        """Return True if the remote is on."""
        return self._state

    @property
    def available(self):
        """Return True if the remote is available."""
        return self._device.update_manager.available

    @property
    def should_poll(self):
        """Return True if the remote has to be polled for state."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LEARN_COMMAND

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }

    def get_code(self, command, device):
        """Return a code and a boolean indicating a toggle command.

        If the command starts with `b64:`, extract the code from it.
        Otherwise, extract the code from the dictionary, using the device
        and command as keys.

        You need to change the flag whenever a toggle command is sent
        successfully. Use `self._flags[device] ^= 1`.
        """
        if command.startswith("b64:"):
            code, is_toggle_cmd = command[4:], False

        else:
            if device is None:
                raise KeyError("You need to specify a device")

            try:
                code = self._codes[device][command]
            except KeyError as err:
                raise KeyError("Command not found") from err

            # For toggle commands, alternate between codes in a list.
            if isinstance(code, list):
                code = code[self._flags[device]]
                is_toggle_cmd = True
            else:
                is_toggle_cmd = False

        try:
            return data_packet(code), is_toggle_cmd
        except ValueError as err:
            raise ValueError("Invalid code") from err

    @callback
    def get_flags(self):
        """Return a dictionary of toggle flags.

        A toggle flag indicates whether the remote should send an
        alternative code.
        """
        return self._flags

    async def async_added_to_hass(self):
        """Call when the remote is added to hass."""
        state = await self.async_get_last_state()
        self._state = state is None or state.state == STATE_ON

        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the remote."""
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn on the remote."""
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the remote."""
        self._state = False
        self.async_write_ha_state()

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
        device = kwargs.get(ATTR_DEVICE)
        repeat = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs[ATTR_DELAY_SECS]

        if not self._state:
            return

        should_delay = False

        for _, cmd in product(range(repeat), commands):
            if should_delay:
                await asyncio.sleep(delay)

            try:
                code, is_toggle_cmd = self.get_code(cmd, device)

            except (KeyError, ValueError) as err:
                _LOGGER.error("Failed to send '%s': %s", cmd, err)
                should_delay = False
                continue

            try:
                await self._device.async_request(self._device.api.send_data, code)

            except (AuthorizationError, DeviceOfflineError, OSError) as err:
                _LOGGER.error("Failed to send '%s': %s", command, err)
                break

            except BroadlinkException as err:
                _LOGGER.error("Failed to send '%s': %s", command, err)
                should_delay = False
                continue

            should_delay = True
            if is_toggle_cmd:
                self._flags[device] ^= 1

        self._flag_storage.async_delay_save(self.get_flags, FLAG_SAVE_DELAY)

    async def async_learn_command(self, **kwargs):
        """Learn a list of commands from a remote."""
        kwargs = SERVICE_LEARN_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs[ATTR_DEVICE]
        toggle = kwargs[ATTR_ALTERNATIVE]

        if not self._state:
            return

        should_store = False

        for command in commands:
            try:
                code = await self._async_learn_command(command)
                if toggle:
                    code = [code, await self._async_learn_command(command)]

            except (AuthorizationError, DeviceOfflineError, OSError) as err:
                _LOGGER.error("Failed to learn '%s': %s", command, err)
                break

            except BroadlinkException as err:
                _LOGGER.error("Failed to learn '%s': %s", command, err)
                continue

            self._codes.setdefault(device, {}).update({command: code})
            should_store = True

        if should_store:
            await self._code_storage.async_save(self._codes)

    async def _async_learn_command(self, command):
        """Learn a command from a remote."""
        try:
            await self._device.async_request(self._device.api.enter_learning)

        except (BroadlinkException, OSError) as err:
            _LOGGER.debug("Failed to enter learning mode: %s", err)
            raise

        self.hass.components.persistent_notification.async_create(
            f"Press the '{command}' button.",
            title="Learn command",
            notification_id="learn_command",
        )

        try:
            start_time = utcnow()
            while (utcnow() - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                try:
                    code = await self._device.async_request(self._device.api.check_data)

                except (ReadError, StorageError):
                    continue

                return b64encode(code).decode("utf8")
            raise TimeoutError("No code received")

        finally:
            self.hass.components.persistent_notification.async_dismiss(
                notification_id="learn_command"
            )
