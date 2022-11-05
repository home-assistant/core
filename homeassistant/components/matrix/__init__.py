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
from nio.responses import (
    ErrorResponse,
    JoinError,
    JoinResponse,
    LoginError,
    Response,
    UploadError,
    UploadResponse,
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
from homeassistant.core import Event as HassEvent, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import load_json, save_json

from .const import DOMAIN, FORMAT_HTML, FORMAT_TEXT, SERVICE_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"

CONF_HOMESERVER = "homeserver"
CONF_ROOMS = "rooms"
CONF_COMMANDS = "commands"
CONF_WORD = "word"
CONF_EXPRESSION = "expression"

EVENT_MATRIX_COMMAND = "matrix_command"

DEFAULT_CONTENT_TYPE = "application/octet-stream"

MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT

ATTR_FORMAT = "format"  # optional message format
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
            vol.Optional(CONF_ROOMS): vol.All(cv.ensure_list, [cv.string]),
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
        vol.Optional(ATTR_DATA, default={}): {
            vol.Optional(ATTR_FORMAT, default=DEFAULT_MESSAGE_FORMAT): vol.In(
                MESSAGE_FORMATS
            ),
            vol.Optional(ATTR_IMAGES): vol.All(cv.ensure_list, [cv.string]),
        },
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Matrix bot component."""
    config = config[DOMAIN]

    matrix_bot = MatrixBot(
        hass,
        os.path.join(hass.config.path(), SESSION_FILE),
        config[CONF_HOMESERVER],
        config[CONF_VERIFY_SSL],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_ROOMS],
        config[CONF_COMMANDS],
    )
    hass.data[DOMAIN] = matrix_bot

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        matrix_bot.handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )

    return True


class MatrixBot:
    """The Matrix Bot."""

    _client: AsyncClient

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
        self._auth_tokens: dict[str, str] = {}

        self._homeserver = homeserver
        self._verify_tls = verify_ssl
        self._mx_id = username
        self._password = password

        self._client = AsyncClient(
            homeserver=self._homeserver, user=self._mx_id, ssl=self._verify_tls
        )

        self._listening_rooms = listening_rooms

        self._word_commands: dict[RoomID, dict[WordCommand, ConfigCommand]] = {}
        self._expression_commands: dict[RoomID, list[ConfigCommand]] = {}
        self._load_commands(commands)

        async def stop_client(event: HassEvent) -> None:
            """Run once when Home Assistant stops."""
            if self._client is not None:
                await self._client.close()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        async def handle_startup(event: HassEvent) -> None:
            """Run once when Home Assistant finished startup."""
            self._auth_tokens = await self._get_auth_tokens()
            await self._login()
            await self._join_rooms()
            # Sync once so that we don't respond to past events.
            await self._client.sync(timeout=30_000)

            self._client.add_event_callback(self._handle_room_message, RoomMessageText)

            await self._client.sync_forever(
                timeout=30_000,
                loop_sleep_time=1_000,
            )  # milliseconds.

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_startup)

    def _load_commands(self, commands: list[ConfigCommand]) -> None:
        for command in commands:
            # Set the command for all listening_rooms, unless otherwise specified.
            command.setdefault(CONF_ROOMS, self._listening_rooms)  # type: ignore[misc]

            # COMMAND_SCHEMA guarantees that exactly one of CONF_WORD and CONF_expression are set.
            if (word_command := command.get(CONF_WORD)) is not None:
                for room_id in command[CONF_ROOMS]:  # type: ignore[literal-required]
                    self._word_commands.setdefault(room_id, {})
                    self._word_commands[room_id][word_command] = command  # type: ignore[index]
            else:
                for room_id in command[CONF_ROOMS]:  # type: ignore[literal-required]
                    self._expression_commands.setdefault(room_id, [])
                    self._expression_commands[room_id].append(command)

    async def _handle_room_message(self, room: MatrixRoom, event: Event) -> None:
        """Handle a message sent to a Matrix room."""
        # Corresponds to message type 'm.text'.
        assert isinstance(event, RoomMessageText)

        if event.sender == self._mx_id:
            return
        _LOGGER.debug("Handling message: %s", event.body)

        room_id = RoomID(room.room_id)

        if event.body.startswith("!"):
            # Could trigger a single-word command.
            pieces = event.body.split()
            word = WordCommand(pieces[0].lstrip("!"))

            if command := self._word_commands.get(room_id, {}).get(word):
                event_data = {
                    "command": command[CONF_NAME],
                    "sender": event.sender,
                    "room": room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room.
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
        """Join a room or do nothing if already joined."""
        join_response = await self._client.join(room_id_or_alias)

        if isinstance(join_response, JoinResponse):
            _LOGGER.debug("Joined or already in room '%s'", room_id_or_alias)
        elif isinstance(join_response, JoinError):
            _LOGGER.error(
                "Could not join room '%s': %s",
                room_id_or_alias,
                join_response,
            )

    async def _join_rooms(self) -> None:
        """Join the Matrix rooms that we listen for commands in."""
        rooms = {self._join_room(room_id) for room_id in self._listening_rooms}
        await asyncio.wait(rooms)

    async def _get_auth_tokens(self) -> dict[str, str]:
        """Read sorted authentication tokens from disk."""
        try:
            auth_tokens = await self.hass.async_add_executor_job(
                load_json, self._session_filepath
            )
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

    async def _store_auth_token(self, token: str) -> None:
        """Store authentication token to session and persistent storage."""
        self._auth_tokens[self._mx_id] = token

        await self.hass.async_add_executor_job(
            save_json, self._session_filepath, self._auth_tokens
        )

    async def _login(self) -> None:
        """
        Login to the Matrix homeserver.

        Attempts to use the stored authentication token.
        If that fails, then tries using the password.
        If that also fails, raises LocalProtocolError.
        """

        # If we have an authentication token
        if (token := self._auth_tokens.get(self._mx_id)) is not None:
            response = await self._client.login(token=token)
            _LOGGER.debug("Logging in using stored token")

            if isinstance(response, LoginError):
                _LOGGER.warning(
                    "Login by token failed: %s, %s",
                    response.status_code,
                    response.message,
                )

        # If the token login did not succeed
        if not self._client.logged_in:
            response = await self._client.login(password=self._password)
            _LOGGER.debug("Logging in using password")

            if isinstance(response, LoginError):
                _LOGGER.warning(
                    "Login by password failed: %s, %s",
                    response.status_code,
                    response.message,
                )

        if not self._client.logged_in:
            raise ConfigEntryAuthFailed(
                "Login failed, both token and username/password are invalid"
            )

        await self._store_auth_token(self._client.access_token)

    async def _send_image(self, image_path: str, target_rooms: list[RoomID]) -> None:
        """Upload an image, then send it to all target_rooms."""
        if not self.hass.config.is_allowed_path(image_path):
            _LOGGER.error("Path not allowed: %s", image_path)
            return

        # Get required image metadata.
        image = Image.open(image_path)
        (width, height) = image.size
        mime_type = mimetypes.guess_type(image_path)[0]
        file_stat = await aiofiles.os.stat(image_path)

        _LOGGER.debug("Uploading file from path, %s", image_path)
        async with aiofiles.open(image_path, "r+b") as image_file:
            response = await self._client.upload(
                image_file,
                content_type=mime_type,
                filename=os.path.basename(image_path),
                filesize=file_stat.st_size,
            )
        if isinstance(response, UploadError):
            _LOGGER.error("Unable to upload image to the homeserver: %s", response)
            return

        assert isinstance(response, UploadResponse)
        _LOGGER.debug("Successfully uploaded image to the homeserver")

        content = {
            "body": os.path.basename(image_path),
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "w": width,
                "h": height,
            },
            "msgtype": "m.image",
            "url": response.content_uri,
        }

        for room in target_rooms:
            await self._client.room_send(
                room_id=room, message_type="m.room.message", content=content
            )
            _LOGGER.debug("Image '%s' sent to room '%s'", image_path, room)

    async def _send_message(
        self, message: str, target_rooms: list[RoomID], data: dict | None
    ) -> None:
        """Send a message to the Matrix server."""
        content = {"msgtype": "m.text", "body": message}
        if data is not None and data.get(ATTR_FORMAT) == FORMAT_HTML:
            content |= {"format": "org.matrix.custom.html", "formatted_body": message}
        for target_room in target_rooms:
            response: Response = await self._client.room_send(
                room_id=target_room,
                message_type="m.room.message",
                content=content,
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
            for image_path in data.get(ATTR_IMAGES, []):
                await self._send_image(image_path, target_rooms)

    async def handle_send_message(self, service: ServiceCall) -> None:
        """Handle the send_message service."""
        return await self._send_message(
            service.data[ATTR_MESSAGE],
            service.data[ATTR_TARGET],
            service.data.get(ATTR_DATA),
        )
