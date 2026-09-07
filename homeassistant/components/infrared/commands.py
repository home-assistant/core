"""The known infrared commands.

The commands are a global database, shared by every receiver: the same button
press has to be recognized no matter which receiver picked it up.
"""

from collections.abc import Callable
from functools import partial
from typing import Any, TypedDict, cast, override

import voluptuous as vol

from homeassistant.const import CONF_CODE, CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import collection, config_validation as cv, storage
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import slugify
from homeassistant.util.hass_dict import HassKey

from .code import code_to_frame, frames_match, signal_to_frame
from .const import DOMAIN
from .entity import InfraredReceivedSignal

STORAGE_KEY = f"{DOMAIN}.commands"
STORAGE_VERSION = 1


class InfraredCommandItem(TypedDict):
    """A known infrared command."""

    id: str
    name: str
    code: str


DATA_COMMANDS: HassKey[KnownCommands] = HassKey(f"{DOMAIN}_commands")


def _code(value: Any) -> str:
    """Validate a pronto hex code."""
    code = cv.string(value)
    try:
        code_to_frame(code)
    except ValueError as err:
        raise vol.Invalid(f"Invalid infrared code: {err}") from err
    return code


CREATE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(cv.string, vol.Length(min=1)),
    vol.Required(CONF_CODE): _code,
}

UPDATE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(cv.string, vol.Length(min=1)),
}


class InfraredCommandStorageCollection(collection.DictStorageCollection):
    """Storage collection of known infrared commands."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the command."""
        validated = cast(dict, self.CREATE_SCHEMA(data))
        frame = code_to_frame(validated[CONF_CODE])
        for item in self.data.values():
            # Two presses of a button never report the exact same code, so this
            # is the only place a command captured twice can be caught.
            if frames_match(frame, code_to_frame(item[CONF_CODE])):
                raise vol.Invalid(
                    f"Command is the same infrared command as '{item[CONF_NAME]}'"
                )
        return validated

    @callback
    @override
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the name."""
        return slugify(info[CONF_NAME])

    @override
    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return {**item, **update_data}


class KnownCommands:
    """Read access to the known infrared commands.

    Keeps the frame of every command precomputed, because a received signal is
    matched against all of them.
    """

    def __init__(self, command_collection: InfraredCommandStorageCollection) -> None:
        """Initialize and start following the collection."""
        self._collection = command_collection
        self._frames: dict[str, list[int]] = {}
        self._listeners: list[Callable[[str], None]] = []
        command_collection.async_add_listener(self._async_handle_collection_change)

    async def _async_handle_collection_change(
        self, change_type: str, command_id: str, command: dict
    ) -> None:
        """Update the frames and notify the listeners."""
        if change_type == collection.CHANGE_REMOVED:
            del self._frames[command_id]
        else:
            self._frames[command_id] = code_to_frame(command[CONF_CODE])
        for listener in list(self._listeners):
            listener(command_id)

    @callback
    def get(self, command_id: str) -> InfraredCommandItem | None:
        """Return a command by id."""
        return cast(InfraredCommandItem | None, self._collection.data.get(command_id))

    @callback
    def items(self) -> list[InfraredCommandItem]:
        """Return all commands."""
        return cast(list[InfraredCommandItem], self._collection.async_items())

    @callback
    def names(self) -> list[str]:
        """Return the command names, without duplicates."""
        return list(dict.fromkeys(command[CONF_NAME] for command in self.items()))

    @callback
    def match(self, signal: InfraredReceivedSignal) -> InfraredCommandItem | None:
        """Return the first command a received signal is."""
        frame = signal_to_frame(signal)
        for command_id, expected_frame in self._frames.items():
            if frames_match(frame, expected_frame):
                return self.get(command_id)
        return None

    @callback
    def async_add_listener(self, listener: Callable[[str], None]) -> CALLBACK_TYPE:
        """Listen for changes.

        The listener is called with the id of the command that was added,
        updated or removed. Returns a callable to unsubscribe.
        """
        self._listeners.append(listener)
        return partial(self._listeners.remove, listener)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the known commands and their websocket API."""
    command_collection = InfraredCommandStorageCollection(
        storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
    )
    hass.data[DATA_COMMANDS] = KnownCommands(command_collection)
    await command_collection.async_load()
    collection.DictStorageCollectionWebsocket(
        command_collection,
        f"{DOMAIN}/commands",
        "command",
        CREATE_FIELDS,
        UPDATE_FIELDS,
    ).async_setup(hass)
