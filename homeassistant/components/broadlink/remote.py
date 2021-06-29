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
    NetworkTimeoutError,
    ReadError,
    StorageError,
)
import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DOMAIN as RM_DOMAIN,
    PLATFORM_SCHEMA,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
    SUPPORT_DELETE_COMMAND,
    SUPPORT_LEARN_COMMAND,
    RemoteEntity,
)
from homeassistant.const import CONF_HOST, STATE_OFF
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .entity import BroadlinkEntity
from .helpers import data_packet, import_device

_LOGGER = logging.getLogger(__name__)

LEARNING_TIMEOUT = timedelta(seconds=30)

COMMAND_TYPE_IR = "ir"
COMMAND_TYPE_RF = "rf"
COMMAND_TYPES = [COMMAND_TYPE_IR, COMMAND_TYPE_RF]

CODE_STORAGE_VERSION = 1
FLAG_STORAGE_VERSION = 1

CODE_SAVE_DELAY = 15
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
        vol.Optional(ATTR_COMMAND_TYPE, default=COMMAND_TYPE_IR): vol.In(COMMAND_TYPES),
        vol.Optional(ATTR_ALTERNATIVE, default=False): cv.boolean,
    }
)

SERVICE_DELETE_SCHEMA = COMMAND_SCHEMA.extend(
    {vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1))}
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
    async_add_entities([remote], False)


class BroadlinkRemote(BroadlinkEntity, RemoteEntity, RestoreEntity):
    """Representation of a Broadlink remote."""

    def __init__(self, device, codes, flags):
        """Initialize the remote."""
        super().__init__(device)
        self._coordinator = device.update_manager.coordinator
        self._code_storage = codes
        self._flag_storage = flags
        self._storage_loaded = False
        self._codes = {}
        self._flags = defaultdict(int)
        self._lock = asyncio.Lock()

        self._attr_name = f"{self._device.name} Remote"
        self._attr_is_on = True
        self._attr_supported_features = SUPPORT_LEARN_COMMAND | SUPPORT_DELETE_COMMAND
        self._attr_unique_id = self._device.unique_id

    def _extract_codes(self, commands, device=None):
        """Extract a list of codes.

        If the command starts with `b64:`, extract the code from it.
        Otherwise, extract the code from storage, using the command and
        device as keys.

        The codes are returned in sublists. For toggle commands, the
        sublist contains two codes that must be sent alternately with
        each call.
        """
        code_list = []
        for cmd in commands:
            if cmd.startswith("b64:"):
                codes = [cmd[4:]]

            else:
                if device is None:
                    raise ValueError("You need to specify a device")

                try:
                    codes = self._codes[device][cmd]
                except KeyError as err:
                    raise ValueError(f"Command not found: {repr(cmd)}") from err

                if isinstance(codes, list):
                    codes = codes[:]
                else:
                    codes = [codes]

            for idx, code in enumerate(codes):
                try:
                    codes[idx] = data_packet(code)
                except ValueError as err:
                    raise ValueError(f"Invalid code: {repr(code)}") from err

            code_list.append(codes)
        return code_list

    @callback
    def _get_codes(self):
        """Return a dictionary of codes."""
        return self._codes

    @callback
    def _get_flags(self):
        """Return a dictionary of toggle flags.

        A toggle flag indicates whether the remote should send an
        alternative code.
        """
        return self._flags

    async def async_added_to_hass(self):
        """Call when the remote is added to hass."""
        state = await self.async_get_last_state()
        self._attr_is_on = state is None or state.state != STATE_OFF

        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the remote."""
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn on the remote."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the remote."""
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _async_load_storage(self):
        """Load code and flag storage from disk."""
        # Exception is intentionally not trapped to
        # provide feedback if something fails.
        self._codes.update(await self._code_storage.async_load() or {})
        self._flags.update(await self._flag_storage.async_load() or {})
        self._storage_loaded = True

    async def async_send_command(self, command, **kwargs):
        """Send a list of commands to a device."""
        kwargs[ATTR_COMMAND] = command
        kwargs = SERVICE_SEND_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs.get(ATTR_DEVICE)
        repeat = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs[ATTR_DELAY_SECS]
        service = f"{RM_DOMAIN}.{SERVICE_SEND_COMMAND}"

        if not self._attr_is_on:
            _LOGGER.warning(
                "%s canceled: %s entity is turned off", service, self.entity_id
            )
            return

        if not self._storage_loaded:
            await self._async_load_storage()

        try:
            code_list = self._extract_codes(commands, device)
        except ValueError as err:
            _LOGGER.error("Failed to call %s: %s", service, err)
            raise

        rf_flags = {0xB2, 0xD7}
        if not hasattr(self._device.api, "sweep_frequency") and any(
            c[0] in rf_flags for codes in code_list for c in codes
        ):
            err_msg = f"{self.entity_id} doesn't support sending RF commands"
            _LOGGER.error("Failed to call %s: %s", service, err_msg)
            raise ValueError(err_msg)

        at_least_one_sent = False
        for _, codes in product(range(repeat), code_list):
            if at_least_one_sent:
                await asyncio.sleep(delay)

            if len(codes) > 1:
                code = codes[self._flags[device]]
            else:
                code = codes[0]

            try:
                await self._device.async_request(self._device.api.send_data, code)
            except (BroadlinkException, OSError) as err:
                _LOGGER.error("Error during %s: %s", service, err)
                break

            if len(codes) > 1:
                self._flags[device] ^= 1
            at_least_one_sent = True

        if at_least_one_sent:
            self._flag_storage.async_delay_save(self._get_flags, FLAG_SAVE_DELAY)

    async def async_learn_command(self, **kwargs):
        """Learn a list of commands from a remote."""
        kwargs = SERVICE_LEARN_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        command_type = kwargs[ATTR_COMMAND_TYPE]
        device = kwargs[ATTR_DEVICE]
        toggle = kwargs[ATTR_ALTERNATIVE]
        service = f"{RM_DOMAIN}.{SERVICE_LEARN_COMMAND}"

        if not self._attr_is_on:
            _LOGGER.warning(
                "%s canceled: %s entity is turned off", service, self.entity_id
            )
            return

        if not self._storage_loaded:
            await self._async_load_storage()

        async with self._lock:
            if command_type == COMMAND_TYPE_IR:
                learn_command = self._async_learn_ir_command

            elif hasattr(self._device.api, "sweep_frequency"):
                learn_command = self._async_learn_rf_command

            else:
                err_msg = f"{self.entity_id} doesn't support learning RF commands"
                _LOGGER.error("Failed to call %s: %s", service, err_msg)
                raise ValueError(err_msg)

            should_store = False

            for command in commands:
                try:
                    code = await learn_command(command)
                    if toggle:
                        code = [code, await learn_command(command)]

                except (AuthorizationError, NetworkTimeoutError, OSError) as err:
                    _LOGGER.error("Failed to learn '%s': %s", command, err)
                    break

                except BroadlinkException as err:
                    _LOGGER.error("Failed to learn '%s': %s", command, err)
                    continue

                self._codes.setdefault(device, {}).update({command: code})
                should_store = True

            if should_store:
                await self._code_storage.async_save(self._codes)

    async def _async_learn_ir_command(self, command):
        """Learn an infrared command."""
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

            raise TimeoutError(
                "No infrared code received within "
                f"{LEARNING_TIMEOUT.total_seconds()} seconds"
            )

        finally:
            self.hass.components.persistent_notification.async_dismiss(
                notification_id="learn_command"
            )

    async def _async_learn_rf_command(self, command):
        """Learn a radiofrequency command."""
        try:
            await self._device.async_request(self._device.api.sweep_frequency)

        except (BroadlinkException, OSError) as err:
            _LOGGER.debug("Failed to sweep frequency: %s", err)
            raise

        self.hass.components.persistent_notification.async_create(
            f"Press and hold the '{command}' button.",
            title="Sweep frequency",
            notification_id="sweep_frequency",
        )

        try:
            start_time = utcnow()
            while (utcnow() - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                found = await self._device.async_request(
                    self._device.api.check_frequency
                )
                if found:
                    break
            else:
                await self._device.async_request(
                    self._device.api.cancel_sweep_frequency
                )
                raise TimeoutError(
                    "No radiofrequency found within "
                    f"{LEARNING_TIMEOUT.total_seconds()} seconds"
                )

        finally:
            self.hass.components.persistent_notification.async_dismiss(
                notification_id="sweep_frequency"
            )

        await asyncio.sleep(1)

        try:
            await self._device.async_request(self._device.api.find_rf_packet)

        except (BroadlinkException, OSError) as err:
            _LOGGER.debug("Failed to enter learning mode: %s", err)
            raise

        self.hass.components.persistent_notification.async_create(
            f"Press the '{command}' button again.",
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

            raise TimeoutError(
                "No radiofrequency code received within "
                f"{LEARNING_TIMEOUT.total_seconds()} seconds"
            )

        finally:
            self.hass.components.persistent_notification.async_dismiss(
                notification_id="learn_command"
            )

    async def async_delete_command(self, **kwargs):
        """Delete a list of commands from a remote."""
        kwargs = SERVICE_DELETE_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs[ATTR_DEVICE]
        service = f"{RM_DOMAIN}.{SERVICE_DELETE_COMMAND}"

        if not self._attr_is_on:
            _LOGGER.warning(
                "%s canceled: %s entity is turned off",
                service,
                self.entity_id,
            )
            return

        if not self._storage_loaded:
            await self._async_load_storage()

        try:
            codes = self._codes[device]
        except KeyError as err:
            err_msg = f"Device not found: {repr(device)}"
            _LOGGER.error("Failed to call %s. %s", service, err_msg)
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
                _LOGGER.error("Failed to call %s. %s", service, err_msg)
                raise ValueError(err_msg)

            _LOGGER.error("Error during %s. %s", service, err_msg)

        # Clean up
        if not codes:
            del self._codes[device]
            if self._flags.pop(device, None) is not None:
                self._flag_storage.async_delay_save(self._get_flags, FLAG_SAVE_DELAY)

        self._code_storage.async_delay_save(self._get_codes, CODE_SAVE_DELAY)
