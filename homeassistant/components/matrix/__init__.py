"""The Matrix bot component."""
import logging
import mimetypes
import os
from typing import Any

from matrix_client.client import MatrixRequestError
from nio import (
    AsyncClient,
    LocalProtocolError,
    LoginResponse,
    MatrixRoom,
    RoomMessageText,
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
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import JsonObjectType, load_json_object

from .const import DOMAIN, FORMAT_HTML, FORMAT_TEXT, SERVICE_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"

CONF_HOMESERVER = "homeserver"
CONF_ROOMS = "rooms"
CONF_COMMANDS = "commands"
CONF_WORD = "word"
CONF_EXPRESSION = "expression"

DEFAULT_CONTENT_TYPE = "application/octet-stream"

MESSAGE_FORMATS = [FORMAT_HTML, FORMAT_TEXT]
DEFAULT_MESSAGE_FORMAT = FORMAT_TEXT

EVENT_MATRIX_COMMAND = "matrix_command"

ATTR_FORMAT = "format"  # optional message format
ATTR_IMAGES = "images"  # optional images

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
        await bot.init()
        hass.data[DOMAIN] = bot
    except MatrixRequestError as exception:
        _LOGGER.error("Matrix failed to log in: %s", str(exception))
        return False

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        bot.handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )

    hass.states.async_set("matrix.world", "Paulus")
    return True


class MatrixBot:
    """The Matrix Bot."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_file,
        homeserver,
        verify_ssl,
        username,
        password,
        listening_rooms: list[str],
        commands,
    ) -> None:
        """Set up the client."""
        self.hass = hass

        self._client: AsyncClient = None

        self._session_filepath = config_file
        self._auth_info = self._get_stored_auth_info()

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
        self._word_commands: dict[str, dict[str, dict[str, str]]] = {}

        # Regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list
        self._expression_commands: dict[str, list[Any]] = {}

        for command in commands:
            if not command.get(CONF_ROOMS):
                command[CONF_ROOMS] = listening_rooms

            if command.get(CONF_WORD):
                for room_id in command[CONF_ROOMS]:
                    if room_id not in self._word_commands:
                        self._word_commands[room_id] = {}
                    self._word_commands[room_id][command[CONF_WORD]] = command
            else:
                for room_id in command[CONF_ROOMS]:
                    if room_id not in self._expression_commands:
                        self._expression_commands[room_id] = []
                    self._expression_commands[room_id].append(command)

    async def init(self):
        """Initialie async Matrix Bot."""

        # Log in. This raises a MatrixRequestError if login is unsuccessful
        self._client = await self._login()

        async def stop_client(_):
            """Run once when Home Assistant stops."""
            # asyncio.get_event_loop().stop()
            await self._client.close()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        # Joining rooms potentially does a lot of I/O, so we defer it
        async def handle_startup(_):
            """Run once when Home Assistant finished startup."""
            await self._start_event_loop()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_startup)

    def _handle_room_message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """Handle a message sent to a Matrix room."""

        if event.sender == self._mx_id:
            return

        _LOGGER.debug("Handling message '%s' in room '%s'", event.body, room.room_id)

        room_id = room.room_id
        if event.body[0] == "!":
            # Could trigger a single-word command
            pieces = event.body.split(" ")
            cmd = pieces[0][1:]

            command = self._word_commands.get(room.room_id, {}).get(cmd)
            if command:
                event_data = {
                    "command": command[CONF_NAME],
                    "sender": event.sender,
                    "room": room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room
        for rcommand in self._expression_commands.get(room_id, []):
            match = rcommand[CONF_EXPRESSION].match(event.body)
            if not match:
                continue
            event_data = {
                "command": rcommand[CONF_NAME],
                "sender": event.sender,
                "room": room_id,
                "args": match.groupdict(),
            }
            self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

    async def _join_or_get_room(self, room_id_or_alias):
        """Join a room or get it, if we are already in the room.

        We can't just always call join_room(), since that seems to crash
        the client if we're already in the room.
        """
        rooms = self._client.rooms
        if room_id_or_alias in rooms:
            _LOGGER.debug("Already in room %s", room_id_or_alias)
            return rooms[room_id_or_alias]

        for room in rooms.values():
            if room.room_id not in self._aliases_fetched_for:
                room.update_aliases()
                self._aliases_fetched_for.add(room.room_id)

            if (
                room_id_or_alias in room.aliases
                or room_id_or_alias == room.canonical_alias
            ):
                _LOGGER.debug(
                    "Already in room %s (known as %s)", room.room_id, room_id_or_alias
                )
                return room

        room = await self._client.join(room_id_or_alias)
        _LOGGER.info("Joined room %s (known as %s)", room.room_id, room_id_or_alias)
        return room

    async def _start_event_loop(self):
        """Join the Matrix rooms that we listen for commands in."""
        self._client.add_event_callback(self._handle_room_message, RoomMessageText)
        for room in self._listening_rooms:
            await self._client.join(room)
        await self._client.sync_forever(timeout=30000, full_state=False)

    def _get_stored_auth_info(self) -> JsonObjectType:
        """Read sorted authentication tokens from disk.

        Returns the auth_tokens dictionary.
        """
        try:
            return load_json_object(self._session_filepath)
        except HomeAssistantError as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self._session_filepath,
                str(ex),
            )
            return {}

    def _store_auth_info(self, token: str, device_id: str):
        """Store authentication token to session and persistent storage."""
        self._auth_info[self._mx_id] = {"token": token, "device_id": device_id}

        save_json(self._session_filepath, self._auth_info)

    async def _login(self):
        """Login to the Matrix homeserver and return the client instance."""
        # Attempt to generate a valid client using either of the two possible
        # login methods:
        client = None

        # If we have an authentication token
        try:
            client = await self._login_by_token()
        except KeyError as ex:
            _LOGGER.debug(
                "No saved login data, ex: %s",
                str(ex),
            )

        # If we still don't have a client try password
        if not client:
            client = await self._login_by_password()
            _LOGGER.debug("Logged in using password")

        return client

    async def _login_by_token(self):
        """Login using authentication token and return the client."""
        client = AsyncClient(self._homeserver)

        client.restore_login(
            user_id=self._mx_id,
            device_id=self._auth_info[self._mx_id]["device_id"],
            access_token=self._auth_info[self._mx_id]["token"],
        )

        return client

    async def _login_by_password(self):
        """Login using password authentication and return the client."""
        _client = AsyncClient(
            homeserver=self._homeserver, user=self._mx_id, ssl=self._verify_tls
        )

        resp = await _client.login(self._password)
        # check that we logged in successfully
        if isinstance(resp, LoginResponse):
            self._store_auth_info(resp.access_token, resp.device_id)
        else:
            _LOGGER.error(
                "Login failed, both token and username/password invalid: %d, %s",
                resp.status_code,
                resp.message,
            )

        return _client

    async def _send_image(self, img, target_rooms):
        _LOGGER.debug("Uploading file from path, %s", img)

        if not self.hass.config.is_allowed_path(img):
            _LOGGER.error("Path not allowed: %s", img)
            return
        with open(img, "rb") as upfile:
            imgfile = upfile.read()
        content_type = mimetypes.guess_type(img)[0]
        mxc = await self._client.upload(imgfile, content_type)
        for target_room in target_rooms:
            try:
                # mxc, img, mimetype=content_type
                await self._client.room_send(
                    room_id=target_room,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.image",
                        "body": img,
                        "info": {"mimetype": content_type},
                        "url": mxc.content_uri,
                    },
                )
            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room '%s': %d, %s",
                    target_room,
                    ex.code,
                    ex.content,
                )

    async def _send_message(self, message, data, target_rooms):
        """Send the message to the Matrix server."""
        for target_room in target_rooms:
            try:
                if message is not None:
                    _LOGGER.debug(
                        await self._client.room_send(
                            room_id=target_room,
                            message_type="m.room.message",
                            content={"msgtype": "m.text", "body": message},
                        )
                    )
            except LocalProtocolError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room %s: %s",
                    target_room,
                    ex,
                )

        if ATTR_IMAGES in data:
            for img in data.get(ATTR_IMAGES, []):
                await self._send_image(img, target_rooms)

    async def handle_send_message(self, service: ServiceCall) -> None:
        """Handle the send_message service."""
        await self._send_message(
            service.data.get(ATTR_MESSAGE),
            service.data.get(ATTR_DATA),
            service.data[ATTR_TARGET],
        )
