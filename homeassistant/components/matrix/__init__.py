"""The Matrix bot component."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
import mimetypes
import os
import pathlib
import re
from typing import Final, NewType, Required, TypedDict

import aiofiles.os
from nio import AsyncClient, AsyncClientConfig, Event, MatrixRoom
from nio.events.room_events import RoomMessageText
from nio.exceptions import OlmUnverifiedDeviceError
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
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.json import save_json
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import JsonObjectType, load_json_object

from .const import (
    DOMAIN,
    FORMAT_HTML,
    FORMAT_TEXT,
    SERVICE_SEND_MESSAGE,
    SERVICE_TRUST_BLACKLIST_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"
STORE_DIRECTORY = ".matrixstore"

CONF_HOMESERVER: Final = "homeserver"
CONF_ROOMS: Final = "rooms"
CONF_COMMANDS: Final = "commands"
CONF_WORD: Final = "word"
CONF_EXPRESSION: Final = "expression"

CONF_USERNAME_REGEX = "^@[^:]*:.*"
CONF_ROOMS_REGEX = "^[!|#][^:]*:.*"

EVENT_MATRIX_COMMAND = "matrix_command"

DEFAULT_CONTENT_TYPE = "application/octet-stream"
MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 52428800

MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT

ATTR_FORMAT = "format"  # optional message format
ATTR_IMAGES = "images"  # optional images
ATTR_IMAGE_URLS = "image_urls"  # optional images from url
ATTR_VERIFY_SSL = "verify_ssl"  # optional verify ssl
ATTR_USER_ID = "user_id"
ATTR_DEVICE_ID = "device_id"
ATTR_BLACKLIST = "blacklist"
ATTR_APPLY_ALL_DEVICES = "apply_all_devices"
ATTR_APPLY_ALL_USER_DEVICES = "apply_all_user_devices"
ATTR_ACCESS_TOKEN = "access_token"

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
            vol.Optional(ATTR_IMAGE_URLS): vol.All(cv.ensure_list, [cv.url]),
            vol.Optional(ATTR_VERIFY_SSL, default=True): cv.boolean,
        },
        vol.Required(ATTR_TARGET): vol.All(
            cv.ensure_list, [cv.matches_regex(CONF_ROOMS_REGEX)]
        ),
    }
)

SERVICE_SCHEMA_TRUST_BLACKLIST_DEVICE = vol.Schema(
    {
        vol.Optional(ATTR_USER_ID, default=""): cv.string,
        vol.Optional(ATTR_DEVICE_ID, default=""): cv.string,
        vol.Exclusive(ATTR_APPLY_ALL_DEVICES, "apply_type"): cv.boolean,
        vol.Exclusive(ATTR_APPLY_ALL_USER_DEVICES, "apply_type"): cv.boolean,
        vol.Optional(ATTR_BLACKLIST, default=False): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Matrix bot component."""
    config = config[DOMAIN]

    # Cleanup the old session file. This file is incompatible with the new e2e encryption
    # implementation and will raise a LocalProtocolError. The new session file is stored
    # in .storage and is not backwards compatible with the old session file.
    old_session_file = pathlib.Path(hass.config.path()) / SESSION_FILE
    old_session_file.unlink(missing_ok=True)

    matrix_bot = MatrixBot(
        hass,
        os.path.join(hass.config.path(STORAGE_DIR, STORE_DIRECTORY), SESSION_FILE),
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRUST_BLACKLIST_DEVICE,
        matrix_bot.handle_trust_blacklist_device,
        schema=SERVICE_SCHEMA_TRUST_BLACKLIST_DEVICE,
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

        store_path = pathlib.Path(hass.config.path(STORAGE_DIR, STORE_DIRECTORY))
        store_path.mkdir(parents=True, exist_ok=True)
        self._client = AsyncClient(
            homeserver=self._homeserver,
            user=self._mx_id,
            ssl=self._verify_tls,
            config=AsyncClientConfig(encryption_enabled=True),
            store_path=str(store_path.absolute()),
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

    async def _store_auth_token(self) -> None:
        """Store authentication token to session and persistent storage."""
        self._access_tokens[self._client.user] = {
            ATTR_DEVICE_ID: self._client.device_id,
            ATTR_ACCESS_TOKEN: self._client.access_token,
        }

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
        if (
            token_data := self._access_tokens.get(self._mx_id)
        ) is not None and isinstance(token_data, dict):
            _LOGGER.debug("Restoring login from stored access token")
            self._client.restore_login(
                user_id=self._mx_id,
                device_id=str(token_data[ATTR_DEVICE_ID]),
                access_token=str(token_data[ATTR_ACCESS_TOKEN]),
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
            self._client.load_store()

        if not self._client.logged_in:
            raise ConfigEntryAuthFailed(
                "Login failed, both token and username/password are invalid"
            )

        await self._store_auth_token()

    async def _handle_room_send(
        self, target_room: RoomAnyID, message_type: str, content: dict
    ) -> None:
        """Wrap _client.room_send and handle ErrorResponses."""
        try:
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
        except OlmUnverifiedDeviceError as ex:
            _LOGGER.error("Unverified device: %s", ex)

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

    async def _send_image_url(
        self, image_url: str, target_rooms: Sequence[RoomAnyID], verify_ssl: bool
    ) -> None:
        """Upload an image from a URL, then send it to all target_rooms."""
        # Get required image metadata.
        if not self.hass.config.is_allowed_external_url(image_url):
            _LOGGER.error("URL '%s' not in allow list", image_url)
            return
        session = aiohttp_client.async_get_clientsession(self.hass)
        resp = await session.get(
            image_url, raise_for_status=True, verify_ssl=verify_ssl
        )
        image_type = (
            resp.headers.get("Content-Type")
            or mimetypes.guess_type(image_url)[0]
            or "image/jpeg"
        )
        if (
            int(resp.headers.get("Content-Length", "0"))
            > MAX_ALLOWED_DOWNLOAD_SIZE_BYTES
        ):
            _LOGGER.error(
                "Attachment too large (Content-Length reports %s). Max size: %s"
                " bytes",
                int(str(resp.headers.get("Content-Length"))),
                MAX_ALLOWED_DOWNLOAD_SIZE_BYTES,
            )
            return
        async with aiofiles.tempfile.TemporaryDirectory() as tempdir:
            image_extension = mimetypes.guess_extension(image_type)
            path = pathlib.Path(tempdir) / f"image{image_extension}"
            async with aiofiles.open(path, "wb") as f:
                await f.write(await resp.read())
            await self._send_image(
                str(path.absolute()), target_rooms, skip_check_allowed=True
            )

    async def _send_image(
        self,
        image_path: str,
        target_rooms: Sequence[RoomAnyID],
        skip_check_allowed: bool = False,
    ) -> None:
        """Upload an image, then send it to all target_rooms."""
        if not skip_check_allowed:
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

        if data is not None and len(target_rooms) > 0:
            tasks = []
            if image_paths := data.get(ATTR_IMAGES, []):
                image_tasks = [
                    self.hass.async_create_task(
                        self._send_image(image_path, target_rooms)
                    )
                    for image_path in image_paths
                ]
                tasks.extend(image_tasks)
            if image_urls := data.get(ATTR_IMAGE_URLS, []):
                image_url_tasks = [
                    self.hass.async_create_task(
                        self._send_image_url(
                            image_url, target_rooms, data[ATTR_VERIFY_SSL]
                        )
                    )
                    for image_url in image_urls
                ]
                tasks.extend(image_url_tasks)
            if tasks:
                await asyncio.wait(tasks)

    async def _trust_blacklist_device(
        self,
        blacklist: bool,
        trusted_user_id: str = "",
        trusted_device_id: str = "",
        apply_all_user_devices: bool = False,  # Apply only to specified user's devices
        apply_all_devices: bool = False,  # Apply to all devices regardless of user
    ) -> None:
        """Trust or blacklist a user's device."""
        if (
            sum(
                [
                    trusted_user_id != "" and trusted_device_id != "",
                    apply_all_user_devices,
                    apply_all_devices,
                ]
            )
            != 1
        ):
            _LOGGER.error(
                "Exactly one of trusted_user_id and apply_all_user_devices, "
                "trusted_user_id and trusted_device_id, or apply_all_devices must be specified!"
            )
            return
        if trusted_user_id == "" and apply_all_user_devices:
            _LOGGER.error(
                "A trusted_user_id must be specified when using apply_all_user_devices!"
            )
            return
        for user_id, devices in self._client.device_store.items():
            if not apply_all_devices and trusted_user_id != user_id:
                continue
            for device_id, olm_device in devices.items():
                if (
                    apply_all_devices
                    or apply_all_user_devices
                    or trusted_device_id == device_id
                ):
                    if blacklist:
                        self._client.blacklist_device(olm_device)
                        _LOGGER.debug(
                            "Blacklisting %s from user %s",
                            trusted_device_id,
                            trusted_user_id,
                        )
                    else:
                        self._client.verify_device(olm_device)
                        _LOGGER.debug(
                            "Trusting %s from user %s",
                            trusted_device_id,
                            trusted_user_id,
                        )

    async def handle_trust_blacklist_device(self, service: ServiceCall) -> None:
        """Handle the trust_blacklist_device service."""
        await self._trust_blacklist_device(
            service.data[ATTR_BLACKLIST],
            trusted_user_id=service.data[ATTR_USER_ID],
            trusted_device_id=service.data[ATTR_DEVICE_ID],
            apply_all_devices=service.data.get(ATTR_APPLY_ALL_DEVICES, False),
            apply_all_user_devices=service.data.get(ATTR_APPLY_ALL_USER_DEVICES, False),
        )

    async def handle_send_message(self, service: ServiceCall) -> None:
        """Handle the send_message service."""
        await self._send_message(
            service.data[ATTR_MESSAGE],
            service.data[ATTR_TARGET],
            service.data.get(ATTR_DATA),
        )
