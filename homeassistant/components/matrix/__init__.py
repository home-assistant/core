"""The Matrix bot component."""
from __future__ import annotations

from copy import deepcopy
from functools import partial
import logging
import mimetypes
import os
import re
from types import MappingProxyType
from typing import Any, Final
import uuid

from matrix_client.client import MatrixClient
from matrix_client.errors import MatrixHttpLibError, MatrixRequestError
from matrix_client.room import Room
import voluptuous as vol

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

from .const import (
    CONF_COMMANDS,
    CONF_EXPRESSION,
    CONF_HOMESERVER,
    CONF_ROOMS,
    CONF_WORD,
    DOMAIN,
    SERVICE_SEND_MESSAGE,
    SESSION_FILE,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_CONTENT_TYPE = "application/octet-stream"

EVENT_MATRIX_COMMAND = "matrix_command"

ATTR_IMAGES = "images"  # optional images

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DATA): {
            vol.Optional(ATTR_IMAGES): vol.All(cv.ensure_list, [cv.string]),
        },
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
    }
)


def setup_bot(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Matrix bot component."""

    try:
        config: MappingProxyType[str, Any] = config_entry.data
        bot = MatrixBot(
            hass,
            os.path.join(hass.config.path(), SESSION_FILE),
            config[CONF_HOMESERVER],
            config[CONF_VERIFY_SSL],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config_entry.options.get(CONF_ROOMS, []),
            config_entry.options.get(CONF_COMMANDS, []),
        )
        hass.data[DOMAIN] = bot

    except (MatrixHttpLibError, MatrixRequestError) as exception:
        _LOGGER.error("Matrix failed to log in: %s", str(exception))
        return False

    hass.services.register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        bot.handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Matrix bot from config entry."""

    status: Final[bool] = await hass.async_add_executor_job(
        setup_bot, hass, config_entry
    )

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return status


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload config entry."""

    # Remove the registered service
    hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    # Remove the bot
    del hass.data[DOMAIN]

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    bot: MatrixBot = hass.data[DOMAIN]
    # Update listening rooms
    await hass.async_add_executor_job(
        bot.set_listening_rooms,
        config_entry.options.get(CONF_ROOMS, []),
    )
    # Update listening commands
    await hass.async_add_executor_job(
        bot.set_listening_commands,
        config_entry.options.get(CONF_COMMANDS, []),
    )


class MatrixAuthentication:
    """The authentication part of Matrix Bot, inherited by class MatrixBot."""

    def __init__(
        self,
        config_file: str,
        homeserver: str,
        verify_ssl: bool,
        username: str,
        password: str,
    ) -> None:
        """Set up the authentication part."""
        self._session_filepath: str = config_file
        self._auth_tokens: dict[str, str] = self._get_auth_tokens()

        self._homeserver: str = homeserver
        self._verify_tls: bool = verify_ssl
        self._mx_id: str = username
        self._password: str = password

    def auth_token(self, username: str) -> str | None:
        """Get the authentication token for a specified username from config file."""
        return self._auth_tokens.get(username)

    def login(self) -> MatrixClient:
        """Login to the Matrix homeserver and return the client instance."""
        # Attempt to generate a valid client using either of the two possible
        # login methods:
        client: MatrixClient | str = None

        # If we have an authentication token
        if self._mx_id in self._auth_tokens:
            client = self._login_by_token()

        # If we still don't have a client try password
        if not client:
            # Will throw an exception if it fails to log in
            client = self._login_by_password()

        return client

    def _get_auth_tokens(self):
        """
        Read sorted authentication tokens from disk.

        :return: The auth_tokens dictionary.
        """
        try:
            auth_tokens = load_json(self._session_filepath)

            return auth_tokens
        except HomeAssistantError as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self._session_filepath,
                str(ex),
            )
            return {}

    def _store_auth_token(self, token: str) -> None:
        """Store authentication token to session and persistent storage."""
        self._auth_tokens[self._mx_id] = token

        save_json(self._session_filepath, self._auth_tokens)

    def _login_by_token(self) -> MatrixClient | None:
        """
        Login using authentication token and return the client.

        :return: a MatrixClient if login is successful, otherwise None.
        """

        client: MatrixClient | None = None

        try:
            client = MatrixClient(
                base_url=self._homeserver,
                token=self._auth_tokens[self._mx_id],
                user_id=self._mx_id,
                valid_cert_check=self._verify_tls,
            )
            _LOGGER.debug("Logged in using stored token")

        except MatrixRequestError as ex:
            _LOGGER.warning(
                "Login by token failed, falling back to password: %d, %s",
                ex.code,
                ex.content,
            )

        return client

    def _login_by_password(self) -> MatrixClient:
        """Login using password authentication and return the client."""
        try:
            client: MatrixClient = MatrixClient(
                base_url=self._homeserver, valid_cert_check=self._verify_tls
            )
            client.login_with_password(self._mx_id, self._password)

            self._store_auth_token(client.token)

            _LOGGER.debug("Logged in using password")

        except MatrixRequestError as ex:
            _LOGGER.error(
                "Login failed, both token and username/password invalid: %d, %s",
                ex.code,
                ex.content,
            )
            # Re-raise the error so _setup can catch it
            raise

        return client


class MatrixBot(MatrixAuthentication):
    """The Matrix Bot."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_file: str,
        homeserver: str,
        verify_ssl: bool,
        username: str,
        password: str,
        listening_rooms: list[str] = [],
        commands: list[dict[str, Any]] = [],
    ) -> None:
        """Set up the client."""
        self.hass: HomeAssistant = hass

        # Authentication
        MatrixAuthentication.__init__(
            self,
            config_file=config_file,
            homeserver=homeserver,
            verify_ssl=verify_ssl,
            username=username,
            password=password,
        )

        # Rooms
        self._listening_rooms: list[str] = listening_rooms
        self._listener_ids: dict[str, uuid.UUID] = {}

        # We have to fetch the aliases for every room to make sure we don't
        # join it twice by accident. However, fetching aliases is costly,
        # so we only do it once per room.
        self._aliases_fetched_for: set = set()

        # Word commands are stored dict-of-dict: First dict indexes by room ID
        #  / alias, second dict indexes by the word
        self._word_commands: dict = {}

        # Regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list
        self._expression_commands: dict = {}

        self.set_listening_commands(commands)

        # Log in. This raises a MatrixRequestError if login is unsuccessful
        self._client: MatrixClient = self.login()

        def handle_matrix_exception(exception):
            """Handle exceptions raised inside the Matrix SDK."""
            _LOGGER.error("Matrix exception:\n %s", str(exception))

        self._client.start_listener_thread(exception_handler=handle_matrix_exception)

        def stop_client(_):
            """Run once when Home Assistant stops."""
            self._client.stop_listener_thread()

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        # Joining rooms potentially does a lot of I/O, so we defer it
        def handle_startup(_):
            """Run once when Home Assistant finished startup."""
            self._join_rooms()

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_START, handle_startup)

    def set_listening_rooms(self, listening_rooms: list[str]) -> None:
        """Set listening rooms and update the listeners."""
        # Remove all existing listeners
        self._leave_rooms()
        # Set new listening rooms
        self._listening_rooms = listening_rooms
        # Join rooms in the list
        self._join_rooms()

        _LOGGER.debug(
            f"Listening room list has been updated. Total listening rooms: {len(listening_rooms)}. Current listening rooms: {', '.join((room_id for room_id in listening_rooms))}"
        )

    def set_listening_commands(self, commands: list[dict[str, Any]]) -> None:
        """Set listening commands."""
        self._word_commands = {}
        self._expression_commands = {}

        for _command in commands:
            # Perform a deep copy so saved options will not be changed.
            command: dict[str, Any] = deepcopy(_command)

            if not command.get(CONF_ROOMS):
                command[CONF_ROOMS] = self._listening_rooms

            if command.get(CONF_WORD):
                for room_id in command[CONF_ROOMS]:
                    if room_id not in self._word_commands:
                        self._word_commands[room_id] = {}
                    self._word_commands[room_id][command[CONF_WORD]] = command
            elif command.get(CONF_EXPRESSION):
                command[CONF_EXPRESSION] = re.compile(command[CONF_EXPRESSION])

                for room_id in command[CONF_ROOMS]:
                    if room_id not in self._expression_commands:
                        self._expression_commands[room_id] = []
                    self._expression_commands[room_id].append(command)
            else:
                # Both CONF_WORD and CONF_EXPRESSION are missing. Shouldn't happen.
                _LOGGER.error(
                    f"Could not set up listener for command {command.get(CONF_NAME)}"
                )

        _LOGGER.debug(
            f"Listening command list has been updated. Total listening commands: {len(commands)}. Currently listening commands: {', '.join((str(command.get(CONF_WORD) or command.get(CONF_EXPRESSION)) for command in [*commands]))}"
        )

    def _handle_room_message(self, room_id, room, event):
        """Handle a message sent to a Matrix room."""
        if event["content"]["msgtype"] != "m.text":
            return

        if event["sender"] == self._mx_id:
            return

        _LOGGER.debug("Handling message: %s", event["content"]["body"])

        if event["content"]["body"][0] == "!":
            # Could trigger a single-word command
            pieces = event["content"]["body"].split(" ")
            cmd = pieces[0][1:]

            command = self._word_commands.get(room_id, {}).get(cmd)
            if command:
                event_data = {
                    "command": command[CONF_NAME],
                    "sender": event["sender"],
                    "room": room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room
        for command in self._expression_commands.get(room_id, []):
            match = command[CONF_EXPRESSION].match(event["content"]["body"])
            if not match:
                continue
            event_data = {
                "command": command[CONF_NAME],
                "sender": event["sender"],
                "room": room_id,
                "args": match.groupdict(),
            }
            self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

    def _join_or_get_room(self, room_id_or_alias):
        """Join a room or get it, if we are already in the room.

        We can't just always call join_room(), since that seems to crash
        the client if we're already in the room.
        """
        rooms = self._client.get_rooms()
        if room_id_or_alias in rooms:
            _LOGGER.debug("Already in room %s", room_id_or_alias)
            return rooms[room_id_or_alias]

        for room in rooms.values():
            if room.room_id not in self._aliases_fetched_for:
                room.update_aliases()
                self._aliases_fetched_for.add(room.room_id)

            if room_id_or_alias in room.aliases:
                _LOGGER.debug(
                    "Already in room %s (known as %s)", room.room_id, room_id_or_alias
                )
                return room

        room = self._client.join_room(room_id_or_alias)
        _LOGGER.info("Joined room %s (known as %s)", room.room_id, room_id_or_alias)
        return room

    def _join_rooms(self):
        """Join the Matrix rooms that we listen for commands in."""
        for room_id in self._listening_rooms:
            try:
                room = self._join_or_get_room(room_id)
                listener_id: uuid.UUID = room.add_listener(
                    partial(self._handle_room_message, room_id), "m.room.message"
                )
                self._listener_ids[room_id] = listener_id

            except MatrixRequestError as ex:
                _LOGGER.error("Could not join room %s: %s", room_id, ex)

    def _leave_rooms(self):
        """Remove all command listeners but don't really leave the room."""
        while len(self._listening_rooms) > 0:
            room_id: str = self._listening_rooms.pop()
            room: Room | None = self._client.rooms.get(room_id)

            if not room:
                continue

            room.remove_listener(self._listener_ids[room_id])
            del self._listener_ids[room_id]

    def _send_image(self, img, target_rooms):
        _LOGGER.debug("Uploading file from path, %s", img)

        if not self.hass.config.is_allowed_path(img):
            _LOGGER.error("Path not allowed: %s", img)
            return
        with open(img, "rb") as upfile:
            imgfile = upfile.read()
        content_type = mimetypes.guess_type(img)[0]
        mxc = self._client.upload(imgfile, content_type)
        for target_room in target_rooms:
            try:
                room = self._join_or_get_room(target_room)
                room.send_image(mxc, img)
            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room '%s': %d, %s",
                    target_room,
                    ex.code,
                    ex.content,
                )

    def _send_message(self, message, data, target_rooms):
        """Send the message to the Matrix server."""
        for target_room in target_rooms:
            try:
                room = self._join_or_get_room(target_room)
                if message is not None:
                    _LOGGER.debug(room.send_text(message))
            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room '%s': %d, %s",
                    target_room,
                    ex.code,
                    ex.content,
                )
        if data is not None:
            for img in data.get(ATTR_IMAGES, []):
                self._send_image(img, target_rooms)

    def handle_send_message(self, service: ServiceCall) -> None:
        """Handle the send_message service."""
        self._send_message(
            service.data.get(ATTR_MESSAGE),
            service.data.get(ATTR_DATA),
            service.data[ATTR_TARGET],
        )
