"""Support for Broadlink remotes."""
import asyncio
from base64 import b64encode
from collections import defaultdict
from collections.abc import Iterable
from datetime import timedelta
from itertools import product
import logging
from typing import Any

from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    NetworkTimeoutError,
    ReadError,
    StorageError,
)
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DOMAIN as RM_DOMAIN,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_COMMAND, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import BroadlinkEntity
from .helpers import data_packet

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device, codes, flags):
        """Initialize the remote."""
        super().__init__(device)
        self._code_storage = codes
        self._flag_storage = flags
        self._storage_loaded = False
        self._codes = {}
        self._flags = defaultdict(int)
        self._lock = asyncio.Lock()

        self._attr_is_on = True
        self._attr_supported_features = (
            RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND
        )
        self._attr_unique_id = device.unique_id

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

    async def async_added_to_hass(self) -> None:
        """Call when the remote is added to hass."""
        state = await self.async_get_last_state()
        self._attr_is_on = state is None or state.state != STATE_OFF
        await super().async_added_to_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the remote."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
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

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands to a device."""
        kwargs[ATTR_COMMAND] = command
        kwargs = SERVICE_SEND_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        subdevice = kwargs.get(ATTR_DEVICE)
        repeat = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs[ATTR_DELAY_SECS]
        service = f"{RM_DOMAIN}.{SERVICE_SEND_COMMAND}"
        device = self._device

        if not self._attr_is_on:
            _LOGGER.warning(
                "%s canceled: %s entity is turned off", service, self.entity_id
            )
            return

        if not self._storage_loaded:
            await self._async_load_storage()

        try:
            code_list = self._extract_codes(commands, subdevice)
        except ValueError as err:
            _LOGGER.error("Failed to call %s: %s", service, err)
            raise

        rf_flags = {0xB2, 0xD7}
        if not hasattr(device.api, "sweep_frequency") and any(
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
                code = codes[self._flags[subdevice]]
            else:
                code = codes[0]

            try:
                await device.async_request(device.api.send_data, code)
            except (BroadlinkException, OSError) as err:
                _LOGGER.error("Error during %s: %s", service, err)
                break

            if len(codes) > 1:
                self._flags[subdevice] ^= 1
            at_least_one_sent = True

        if at_least_one_sent:
            self._flag_storage.async_delay_save(self._get_flags, FLAG_SAVE_DELAY)

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a list of commands from a remote."""
        kwargs = SERVICE_LEARN_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        command_type = kwargs[ATTR_COMMAND_TYPE]
        subdevice = kwargs[ATTR_DEVICE]
        toggle = kwargs[ATTR_ALTERNATIVE]
        service = f"{RM_DOMAIN}.{SERVICE_LEARN_COMMAND}"
        device = self._device

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

            elif hasattr(device.api, "sweep_frequency"):
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

                self._codes.setdefault(subdevice, {}).update({command: code})
                should_store = True

            if should_store:
                await self._code_storage.async_save(self._codes)

    async def _async_learn_ir_command(self, command):
        """Learn an infrared command."""
        device = self._device

        try:
            await device.async_request(device.api.enter_learning)

        except (BroadlinkException, OSError) as err:
            _LOGGER.debug("Failed to enter learning mode: %s", err)
            raise

        persistent_notification.async_create(
            self.hass,
            f"Press the '{command}' button.",
            title="Learn command",
            notification_id="learn_command",
        )

        try:
            start_time = dt_util.utcnow()
            while (dt_util.utcnow() - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                try:
                    code = await device.async_request(device.api.check_data)
                except (ReadError, StorageError):
                    continue
                return b64encode(code).decode("utf8")

            raise TimeoutError(
                "No infrared code received within "
                f"{LEARNING_TIMEOUT.total_seconds()} seconds"
            )

        finally:
            persistent_notification.async_dismiss(
                self.hass, notification_id="learn_command"
            )

    async def _async_learn_rf_command(self, command):
        """Learn a radiofrequency command."""
        device = self._device

        try:
            await device.async_request(device.api.sweep_frequency)

        except (BroadlinkException, OSError) as err:
            _LOGGER.debug("Failed to sweep frequency: %s", err)
            raise

        persistent_notification.async_create(
            self.hass,
            f"Press and hold the '{command}' button.",
            title="Sweep frequency",
            notification_id="sweep_frequency",
        )

        try:
            start_time = dt_util.utcnow()
            while (dt_util.utcnow() - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                found = await device.async_request(device.api.check_frequency)
                if found:
                    break
            else:
                await device.async_request(device.api.cancel_sweep_frequency)
                raise TimeoutError(
                    "No radiofrequency found within "
                    f"{LEARNING_TIMEOUT.total_seconds()} seconds"
                )

        finally:
            persistent_notification.async_dismiss(
                self.hass, notification_id="sweep_frequency"
            )

        await asyncio.sleep(1)

        try:
            await device.async_request(device.api.find_rf_packet)

        except (BroadlinkException, OSError) as err:
            _LOGGER.debug("Failed to enter learning mode: %s", err)
            raise

        persistent_notification.async_create(
            self.hass,
            f"Press the '{command}' button again.",
            title="Learn command",
            notification_id="learn_command",
        )

        try:
            start_time = dt_util.utcnow()
            while (dt_util.utcnow() - start_time) < LEARNING_TIMEOUT:
                await asyncio.sleep(1)
                try:
                    code = await device.async_request(device.api.check_data)
                except (ReadError, StorageError):
                    continue
                return b64encode(code).decode("utf8")

            raise TimeoutError(
                "No radiofrequency code received within "
                f"{LEARNING_TIMEOUT.total_seconds()} seconds"
            )

        finally:
            persistent_notification.async_dismiss(
                self.hass, notification_id="learn_command"
            )

    async def async_delete_command(self, **kwargs: Any) -> None:
        """Delete a list of commands from a remote."""
        kwargs = SERVICE_DELETE_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        subdevice = kwargs[ATTR_DEVICE]
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
            codes = self._codes[subdevice]
        except KeyError as err:
            err_msg = f"Device not found: {repr(subdevice)}"
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
            del self._codes[subdevice]
            if self._flags.pop(subdevice, None) is not None:
                self._flag_storage.async_delay_save(self._get_flags, FLAG_SAVE_DELAY)

        self._code_storage.async_delay_save(self._get_codes, CODE_SAVE_DELAY)
