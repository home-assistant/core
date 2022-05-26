"""The Matrix bot component."""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import re
from typing import NewType, TypedDict

from PIL import Image
import aiofiles.os
from nio import AsyncClient, Event, MatrixRoom
from nio.events.room_events import RoomMessageText
from nio.exceptions import LocalProtocolError, RemoteProtocolError
from nio.responses import (
    ErrorResponse,
    JoinError,
    JoinResponse,
    LoginError,
    Response,
    UploadError,
)
import voluptuous as vol

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
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
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import load_json, save_json

from .const import DOMAIN, SERVICE_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"

CONF_HOMESERVER = "homeserver"
CONF_ROOMS = "rooms"
CONF_COMMANDS = "commands"
CONF_WORD = "word"
CONF_EXPRESSION = "expression"

DEFAULT_CONTENT_TYPE = "application/octet-stream"

EVENT_MATRIX_COMMAND = "matrix_command"

ATTR_IMAGES = "images"  # optional images

WordCommand = NewType("WordCommand", str)
ExpressionCommand = NewType("ExpressionCommand", re.Pattern)
RoomID = NewType("RoomID", str)


class ConfigCommand(TypedDict, total=False):
    """Corresponds to a single COMMAND_SCHEMA."""

    name: str  # CONF_NAME
    rooms: list[RoomID] | None  # CONF_ROOMS
    word: WordCommand | None  # CONF_WORD
    expression: ExpressionCommand | None  # CONF_EXPRESSION


COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_WORD, "trigger"): cv.string,
            vol.Exclusive(CONF_EXPRESSION, "trigger"): cv.is_regex,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_ROOMS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        }
    ),
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION),
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOMESERVER): cv.url,
                vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
                vol.Required(CONF_USERNAME): cv.matches_regex("@[^:]*:.*"),
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_ROOMS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_COMMANDS, default=[]): [COMMAND_SCHEMA],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DATA): {
            vol.Optional(ATTR_IMAGES): vol.All(cv.ensure_list, [cv.string]),
        },
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Matrix bot component."""
    config = config[DOMAIN]

    try:
        bot = MatrixBot(
            hass,
            os.path.join(hass.config.path(), SESSION_FILE),
            config[CONF_HOMESERVER],
            config[CONF_VERIFY_SSL],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_ROOMS],
            config[CONF_COMMANDS],
        )
        hass.data[DOMAIN] = bot
    except LocalProtocolError as exception:
        _LOGGER.exception("Matrix failed to log in: %s", str(exception))
        return False

    hass.services.register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        bot.handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )

    return True


class MatrixBot:
    """The Matrix Bot."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_file: str,
        homeserver: str,
        verify_ssl: bool,
        username: str,
        password: str,
        listening_rooms: list[RoomID],
        commands: list[ConfigCommand],
    ) -> None:
        """Set up the client."""
        self.hass = hass

        self._session_filepath = config_file
        self._auth_tokens = self._get_auth_tokens()

        self._homeserver = homeserver
        self._verify_tls = verify_ssl
        self._mx_id = username
        self._password = password

        self._listening_rooms = listening_rooms

        # We have to fetch the aliases for every room to make sure we don't
        # join it twice by accident. However, fetching aliases is costly,
        # so we only do it once per room.
        self._aliases_fetched_for: set[str] = set()

        # Word commands are stored dict-of-dict: First dict indexes by room ID
        #  / alias, second dict indexes by the word
        self._word_commands: dict[RoomID, dict[WordCommand, ConfigCommand]] = {}

        # Regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list
        self._expression_commands: dict[RoomID, list[ConfigCommand]] = {}

        for command in commands:
            # Set the command for all listening_rooms, if not otherwise specified.
            command.setdefault(CONF_ROOMS, listening_rooms)  # type: ignore[misc]

            # COMMAND_SCHEMA guarantees that exactly one of CONF_WORD and CONF_expression are set.
            if (word_command := command.get(CONF_WORD)) is not None:
                for room_id in command[CONF_ROOMS]:  # type: ignore[literal-required]
                    self._word_commands.setdefault(room_id, {})
                    self._word_commands[room_id][word_command] = command  # type: ignore[index]
            else:
                for room_id in command[CONF_ROOMS]:  # type: ignore[literal-required]
                    self._expression_commands.setdefault(room_id, [])
                    self._expression_commands[room_id].append(command)

        # Log in. This raises a MatrixRequestError if login is unsuccessful
        self._login()

        # async def handle_matrix_exception(exception):
        #     """Handle exceptions raised inside the Matrix SDK."""
        #     _LOGGER.error("Matrix exception:\n %s", str(exception))
        #
        # self._client.start_listener_thread(exception_handler=handle_matrix_exception)

        async def stop_client(_) -> None:
            """Run once when Home Assistant stops."""
            return await self._client.close()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        # Joining rooms potentially does a lot of I/O, so we defer it
        async def handle_startup(_) -> None:
            """Run once when Home Assistant finished startup."""
            await self._join_rooms()
            self._client.add_event_callback(self._handle_room_message, RoomMessageText)

            return await self._client.sync_forever(timeout=30_000)  # milliseconds

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_startup)

    async def _handle_room_message(self, room: MatrixRoom, event: Event) -> None:
        """Handle a message sent to a Matrix room."""
        assert isinstance(
            event, RoomMessageText
        )  # Corresponds to message type 'm.text'

        if event.sender == self._mx_id:
            return
        _LOGGER.debug("Handling message: %s", event.body)

        room_id = RoomID(room.room_id)

        if event.body.startswith("!"):
            # Could trigger a single-word command
            pieces = event.body.split()
            cmd = WordCommand(pieces[0].rstrip("!"))

            if command := self._word_commands.get(room_id, {}).get(cmd):
                event_data = {
                    "command": command[CONF_NAME],
                    "sender": event.sender,
                    "room": room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room
        for command in self._expression_commands.get(room_id, []):
            match: re.Match = command[CONF_EXPRESSION].match(event.body)  # type: ignore[literal-required]
            if not match:
                continue
            event_data = {
                "command": command[CONF_NAME],
                "sender": event.sender,
                "room": room_id,
                "args": match.groupdict(),
            }
            self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, event_data)

    async def _join_room(self, room_id_or_alias: str) -> None:
        """Join a room or get it, if we are already in the room."""
        join_response = await self._client.join(room_id_or_alias)

        if isinstance(join_response, JoinResponse):
            _LOGGER.debug("Joined or already in room %s", room_id_or_alias)
        elif isinstance(join_response, JoinError):
            raise RemoteProtocolError(
                f"Could not join room '{room_id_or_alias}': {join_response}"
            )

    async def _join_rooms(self):
        """Join the Matrix rooms that we listen for commands in."""
        rooms = {self._join_room(room_id) for room_id in self._listening_rooms}
        try:
            await asyncio.wait(rooms)
        except RemoteProtocolError as exception:
            _LOGGER.exception(str(exception))

    def _get_auth_tokens(self) -> dict[str, str]:
        """
        Read sorted authentication tokens from disk.

        Returns the auth_tokens dictionary.
        """
        try:
            auth_tokens = load_json(self._session_filepath)
            assert isinstance(auth_tokens, dict)
        except AssertionError:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: does not meet expected schema",
                self._session_filepath,
            )
        except HomeAssistantError as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self._session_filepath,
                str(ex),
            )
        else:
            return auth_tokens
        return {}

    def _store_auth_token(self, token: str):
        """Store authentication token to session and persistent storage."""
        self._auth_tokens[self._mx_id] = token

        save_json(self._session_filepath, self._auth_tokens)

    async def _login(self):
        """Login to the Matrix homeserver and return the client instance."""
        # Attempt to generate a valid client using either of the two possible
        # login methods:

        client = AsyncClient(
            homeserver=self._homeserver, user=self._mx_id, ssl=self._verify_tls
        )

        # If we have an authentication token
        if token := self._auth_tokens.get(self._mx_id) is not None:
            response = await client.login(token=token)
            _LOGGER.debug("Logging in using stored token")

            if isinstance(response, LoginError):
                _LOGGER.warning(
                    "Login by token failed, falling back to password: %d, %s",
                    response.status_code,
                    response.message,
                )

        # If the token login did not succeed
        if not client.logged_in:
            response = await client.login(password=self._password)
            _LOGGER.debug("Logging in using password")

            if isinstance(response, LoginError):
                _LOGGER.warning(
                    "Login by password failed: %d, %s",
                    response.status_code,
                    response.message,
                )

        if not client.logged_in:
            raise LocalProtocolError(
                "Login failed, both token and username/password invalid."
            )

        self._client = client

    async def _send_image(self, img: str, target_rooms: list[RoomID]) -> None:
        if not self.hass.config.is_allowed_path(img):
            _LOGGER.error("Path not allowed: %s", img)
            return

        # Get required image metadata.
        image = Image.open(img)
        (width, height) = image.size
        mime_type = mimetypes.guess_type(img)[0]

        file_stat = await aiofiles.os.stat(img)

        _LOGGER.debug("Uploading file from path, %s", img)
        async with aiofiles.open(img, "r+b") as file:
            response, _ = await self._client.upload(
                file,
                content_type=mime_type,
                filename=os.path.basename(img),
                filesize=file_stat.st_size,
            )
        if isinstance(response, UploadError):
            _LOGGER.error("Unable to upload image to homeserver: %s", response)
            return

        content = {
            "body": os.path.basename(img),
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "w": width,
                "h": height,
            },
            "msgtype": "m.image",
            "url": response.content_uri,
        }

        image_sends = {
            self._client.room_send(
                room_id=room, message_type="m.room.message", content=content
            )
            for room in target_rooms
        }
        await asyncio.wait(image_sends)

    async def _send_message(
        self, message: str, data: dict | None, target_rooms: list[RoomID]
    ):
        """Send the message to the Matrix server."""
        for target_room in target_rooms:
            response: Response = await self._client.room_send(
                room_id=target_room,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": message},
            )
            if isinstance(response, ErrorResponse):
                _LOGGER.error(
                    "Unable to deliver message to room '%s': %s",
                    target_room,
                    response,
                )
            else:
                _LOGGER.debug("Message delivered to room '%s'", target_room)

        if data is not None and len(target_rooms) > 0:
            for img in data.get(ATTR_IMAGES, []):
                await self._send_image(img, target_rooms)

    async def handle_send_message(self, service: ServiceCall) -> None:
        """Handle the send_message service."""
        return await self._send_message(
            service.data.get(ATTR_MESSAGE),  # type: ignore[arg-type]
            service.data.get(ATTR_DATA),
            service.data[ATTR_TARGET],
        )
