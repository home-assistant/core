"""The Matrix bot component."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
import mimetypes
import os
import re
from typing import Final, NewType, Required, TypedDict

import aiofiles.os
from nio import AsyncClient, Event, MatrixRoom
from nio.events.room_events import RoomMessageText
from nio.responses import (
    ErrorResponse,
    JoinError,
    JoinResponse,
    LoginError,
    Response,
    RoomResolveAliasResponse,
    UploadError,
    UploadResponse,
    WhoamiError,
    WhoamiResponse,
)
from PIL import Image
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
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import JsonObjectType, load_json_object

from .const import DOMAIN, FORMAT_HTML, FORMAT_TEXT, SERVICE_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"

CONF_HOMESERVER: Final = "homeserver"
CONF_ROOMS: Final = "rooms"
CONF_COMMANDS: Final = "commands"
CONF_WORD: Final = "word"
CONF_EXPRESSION: Final = "expression"

CONF_USERNAME_REGEX = "^@[^:]*:.*"
CONF_ROOMS_REGEX = "^[!|#][^:]*:.*"

EVENT_MATRIX_COMMAND = "matrix_command"

DEFAULT_CONTENT_TYPE = "application/octet-stream"

MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT

ATTR_FORMAT = "format"  # optional message format
ATTR_IMAGES = "images"  # optional images

WordCommand = NewType("WordCommand", str)
ExpressionCommand = NewType("ExpressionCommand", re.Pattern)
RoomAlias = NewType("RoomAlias", str)  # Starts with "#"
RoomID = NewType("RoomID", str)  # Starts with "!"
RoomAnyID = RoomID | RoomAlias


class ConfigCommand(TypedDict, total=False):
    """Corresponds to a single COMMAND_SCHEMA."""

    name: Required[str]  # CONF_NAME
    rooms: list[RoomID]  # CONF_ROOMS
    word: WordCommand  # CONF_WORD
    expression: ExpressionCommand  # CONF_EXPRESSION


COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(CONF_WORD, "trigger"): cv.string,
            vol.Exclusive(CONF_EXPRESSION, "trigger"): cv.is_regex,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_ROOMS): vol.All(
                cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
            ),
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
                vol.Required(CONF_USERNAME): cv.matches_regex(CONF_USERNAME_REGEX),
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_ROOMS, default=[]): vol.All(
                    cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
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
        vol.Required(ATTR_TARGET): vol.All(
            cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
        ),
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
        listening_rooms: list[RoomAnyID],
        commands: list[ConfigCommand],
    ) -> None:
        """Set up the client."""
        self.hass = hass

        self._session_filepath = config_file
        self._access_tokens: JsonObjectType = {}

        self._homeserver = homeserver
        self._verify_tls = verify_ssl
        self._mx_id = username
        self._password = password

        self._client = AsyncClient(
            homeserver=self._homeserver, user=self._mx_id, ssl=self._verify_tls
        )

        self._listening_rooms: dict[RoomAnyID, RoomID] = {}
        self._word_commands: dict[RoomID, dict[WordCommand, ConfigCommand]] = {}
        self._expression_commands: dict[RoomID, list[ConfigCommand]] = {}
        self._unparsed_commands = commands

        async def stop_client(event: HassEvent) -> None:
            """Run once when Home Assistant stops."""
            if self._client is not None:
                await self._client.close()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        async def handle_startup(event: HassEvent) -> None:
            """Run once when Home Assistant finished startup."""
            self._access_tokens = await self._get_auth_tokens()
            await self._login()
            await self._resolve_room_aliases(listening_rooms)
            self._load_commands(commands)
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
            if rooms := command.get(CONF_ROOMS):
                command[CONF_ROOMS] = [self._listening_rooms[room] for room in rooms]
            else:
                command[CONF_ROOMS] = list(self._listening_rooms.values())

            # COMMAND_SCHEMA guarantees that exactly one of CONF_WORD and CONF_EXPRESSION are set.
            if (word_command := command.get(CONF_WORD)) is not None:
                for room_id in command[CONF_ROOMS]:
                    self._word_commands.setdefault(room_id, {})
                    self._word_commands[room_id][word_command] = command
            else:
                for room_id in command[CONF_ROOMS]:
                    self._expression_commands.setdefault(room_id, [])
                    self._expression_commands[room_id].append(command)

    async def _handle_room_message(self, room: MatrixRoom, message: Event) -> None:
        """Handle a message sent to a Matrix room."""
        # Corresponds to message type 'm.text' and NOT other RoomMessage subtypes, like 'm.notice' and 'm.emote'.
        if not isinstance(message, RoomMessageText):
            return
        # Don't respond to our own messages.
        if message.sender == self._mx_id:
            return
        _LOGGER.debug("Handling message: %s", message.body)

        room_id = RoomID(room.room_id)

        if message.body.startswith("!"):
            # Could trigger a single-word command.
            pieces = message.body.split()
            word = WordCommand(pieces[0].lstrip("!"))

            if command := self._word_commands.get(room_id, {}).get(word):
                message_data = {
                    "command": command[CONF_NAME],
                    "sender": message.sender,
                    "room": room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, message_data)

        # After single-word commands, check all regex commands in the room.
        for command in self._expression_commands.get(room_id, []):
            match = command[CONF_EXPRESSION].match(message.body)
            if not match:
                continue
            message_data = {
                "command": command[CONF_NAME],
                "sender": message.sender,
                "room": room_id,
                "args": match.groupdict(),
            }
            self.hass.bus.async_fire(EVENT_MATRIX_COMMAND, message_data)

    async def _resolve_room_alias(
        self, room_alias_or_id: RoomAnyID
    ) -> dict[RoomAnyID, RoomID]:
        """Resolve a single RoomAlias if needed."""
        if room_alias_or_id.startswith("!"):
            room_id = RoomID(room_alias_or_id)
            _LOGGER.debug("Will listen to room_id '%s'", room_id)
        elif room_alias_or_id.startswith("#"):
            room_alias = RoomAlias(room_alias_or_id)
            resolve_response = await self._client.room_resolve_alias(room_alias)
            if isinstance(resolve_response, RoomResolveAliasResponse):
                room_id = RoomID(resolve_response.room_id)
                _LOGGER.debug(
                    "Will listen to room_alias '%s' as room_id '%s'",
                    room_alias_or_id,
                    room_id,
                )
            else:
                _LOGGER.error(
                    "Could not resolve '%s' to a room_id: '%s'",
                    room_alias_or_id,
                    resolve_response,
                )
                return {}
        # The config schema guarantees it's a valid room alias or id, so room_id is always set.
        return {room_alias_or_id: room_id}

    async def _resolve_room_aliases(self, listening_rooms: list[RoomAnyID]) -> None:
        """Resolve any RoomAliases into RoomIDs for the purpose of client interactions."""
        resolved_rooms = [
            self.hass.async_create_task(self._resolve_room_alias(room_alias_or_id))
            for room_alias_or_id in listening_rooms
        ]
        for resolved_room in asyncio.as_completed(resolved_rooms):
            self._listening_rooms |= await resolved_room

    async def _join_room(self, room_id: RoomID, room_alias_or_id: RoomAnyID) -> None:
        """Join a room or do nothing if already joined."""
        join_response = await self._client.join(room_id)

        if isinstance(join_response, JoinResponse):
            _LOGGER.debug("Joined or already in room '%s'", room_alias_or_id)
        elif isinstance(join_response, JoinError):
            _LOGGER.error(
                "Could not join room '%s': %s",
                room_alias_or_id,
                join_response,
            )

    async def _join_rooms(self) -> None:
        """Join the Matrix rooms that we listen for commands in."""
        rooms = [
            self.hass.async_create_task(self._join_room(room_id, room_alias_or_id))
            for room_alias_or_id, room_id in self._listening_rooms.items()
        ]
        await asyncio.wait(rooms)

    async def _get_auth_tokens(self) -> JsonObjectType:
        """Read sorted authentication tokens from disk."""
        try:
            return load_json_object(self._session_filepath)
        except HomeAssistantError as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self._session_filepath,
                str(ex),
            )
            return {}

    async def _store_auth_token(self, token: str) -> None:
        """Store authentication token to session and persistent storage."""
        self._access_tokens[self._mx_id] = token

        await self.hass.async_add_executor_job(
            save_json,
            self._session_filepath,
            self._access_tokens,
            True,  # private=True
        )

    async def _login(self) -> None:
        """Log in to the Matrix homeserver.

        Attempts to use the stored access token.
        If that fails, then tries using the password.
        If that also fails, raises LocalProtocolError.
        """

        # If we have an access token
        if (token := self._access_tokens.get(self._mx_id)) is not None:
            _LOGGER.debug("Restoring login from stored access token")
            self._client.restore_login(
                user_id=self._client.user_id,
                device_id=self._client.device_id,
                access_token=token,
            )
            response = await self._client.whoami()
            if isinstance(response, WhoamiError):
                _LOGGER.warning(
                    "Restoring login from access token failed: %s, %s",
                    response.status_code,
                    response.message,
                )
                self._client.access_token = (
                    ""  # Force a soft-logout if the homeserver didn't.
                )
            elif isinstance(response, WhoamiResponse):
                _LOGGER.debug(
                    "Successfully restored login from access token: user_id '%s', device_id '%s'",
                    response.user_id,
                    response.device_id,
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

    async def _handle_room_send(
        self, target_room: RoomAnyID, message_type: str, content: dict
    ) -> None:
        """Wrap _client.room_send and handle ErrorResponses."""
        response: Response = await self._client.room_send(
            room_id=self._listening_rooms.get(target_room, target_room),
            message_type=message_type,
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

    async def _handle_multi_room_send(
        self, target_rooms: Sequence[RoomAnyID], message_type: str, content: dict
    ) -> None:
        """Wrap _handle_room_send for multiple target_rooms."""
        _tasks = []
        for target_room in target_rooms:
            _tasks.append(
                self.hass.async_create_task(
                    self._handle_room_send(
                        target_room=target_room,
                        message_type=message_type,
                        content=content,
                    )
                )
            )
        await asyncio.wait(_tasks)

    async def _send_image(
        self, image_path: str, target_rooms: Sequence[RoomAnyID]
    ) -> None:
        """Upload an image, then send it to all target_rooms."""
        _is_allowed_path = await self.hass.async_add_executor_job(
            self.hass.config.is_allowed_path, image_path
        )
        if not _is_allowed_path:
            _LOGGER.error("Path not allowed: %s", image_path)
            return

        # Get required image metadata.
        image = await self.hass.async_add_executor_job(Image.open, image_path)
        (width, height) = image.size
        mime_type = mimetypes.guess_type(image_path)[0]
        file_stat = await aiofiles.os.stat(image_path)

        _LOGGER.debug("Uploading file from path, %s", image_path)
        async with aiofiles.open(image_path, "r+b") as image_file:
            response, _ = await self._client.upload(
                image_file,
                content_type=mime_type,
                filename=os.path.basename(image_path),
                filesize=file_stat.st_size,
            )
        if isinstance(response, UploadError):
            _LOGGER.error("Unable to upload image to the homeserver: %s", response)
            return
        if isinstance(response, UploadResponse):
            _LOGGER.debug("Successfully uploaded image to the homeserver")
        else:
            _LOGGER.error(
                "Unknown response received when uploading image to homeserver: %s",
                response,
            )
            return

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

        await self._handle_multi_room_send(
            target_rooms=target_rooms, message_type="m.room.message", content=content
        )

    async def _send_message(
        self, message: str, target_rooms: list[RoomAnyID], data: dict | None
    ) -> None:
        """Send a message to the Matrix server."""
        content = {"msgtype": "m.text", "body": message}
        if data is not None and data.get(ATTR_FORMAT) == FORMAT_HTML:
            content |= {"format": "org.matrix.custom.html", "formatted_body": message}

        await self._handle_multi_room_send(
            target_rooms=target_rooms, message_type="m.room.message", content=content
        )

        if (
            data is not None
            and (image_paths := data.get(ATTR_IMAGES, []))
            and len(target_rooms) > 0
        ):
            image_tasks = [
                self.hass.async_create_task(self._send_image(image_path, target_rooms))
                for image_path in image_paths
            ]
            await asyncio.wait(image_tasks)

    async def handle_send_message(self, service: ServiceCall) -> None:
        """Handle the send_message service."""
        await self._send_message(
            service.data[ATTR_MESSAGE],
            service.data[ATTR_TARGET],
            service.data.get(ATTR_DATA),
        )
