"""The Matrix bot component."""

import asyncio
import logging
import os
from tempfile import NamedTemporaryFile
from time import sleep

from PIL import Image
import aiofiles
import aiofiles.os
import aiohttp
import magic
from markdown import markdown
from nio import (
    AsyncClient,
    AsyncClientConfig,
    JoinResponse,
    LoginError,
    MatrixRoom,
    ProtocolError,
    RoomMessageText,
    RoomResolveAliasResponse,
    RoomSendResponse,
    SendRetryError,
    UploadResponse,
)
import voluptuous as vol

from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TARGET
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SERVICE_SEND_IMAGE, SERVICE_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"

CONF_HOMESERVER = "homeserver"
CONF_MARKDOWN = "markdown"
CONF_ROOMS = "rooms"
CONF_COMMANDS = "commands"
CONF_WORD = "word"
CONF_EXPRESSION = "expression"
CONF_CONVERSATION = "conversation"

ATTR_MARKDOWN = "markdown"
ATTR_NOTICE = "notice"
ATTR_FILE = "file"
ATTR_URL = "url"

EVENT_MATRIX_COMMAND = "matrix_command"

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

CONVERSATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ROOMS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
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
                vol.Optional(CONF_CONVERSATION, default={}): CONVERSATION_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_MARKDOWN, default=False): cv.boolean,
        vol.Optional(ATTR_NOTICE, default=False): cv.boolean,
    }
)


SERVICE_SCHEMA_SEND_IMAGE = vol.Schema(
    {
        vol.Optional(ATTR_FILE): cv.string,
        vol.Optional(ATTR_URL): cv.string,
        vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup(hass, config):
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
            config[CONF_CONVERSATION],
        )

        # Start listener in the background
        await bot.login()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, bot.close)
        asyncio.create_task(bot.startup_and_listen())

        hass.data[DOMAIN] = bot

    except ProtocolError as exception:
        _LOGGER.error("Matrix failed to log in: %s", str(exception))
        return False

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        bot.handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_IMAGE,
        bot.handle_send_image,
        schema=SERVICE_SCHEMA_SEND_IMAGE,
    )
    _LOGGER.debug("Matrix component ready to use.")
    return True


class MatrixBot:
    """Matrix bot."""

    def __init__(
        self,
        hass,
        config_file,
        homeserver,
        verify_ssl,
        username,
        password,
        listening_rooms,
        commands,
        conversation,
    ):
        """Matrix bot.

        Args:
          hass: The homeassistant object
          config_file: The path for the matrix bot (generated dynamically)
          homeserver: The url for the matrix homeserver
          verify_ssl: True if the bot should check the validity
                      of the SSL certificate otherwise False
          username: The username of the bot (like: @bot:matrix.org)
          password: The user's password
          listening_room: The list of the rooms the bot should listen in
          commands: COMMAND_SCHEMA like object from the configuration
          conversation: CONVERSATION_SCHEMA like object from the
                        configuration
        """
        self.hass = hass

        self._session_filepath = config_file

        self._homeserver = homeserver
        self._verify_tls = verify_ssl
        self._mx_id = username
        self._password = password
        self._device_id = "hamatrix"
        self._listening_rooms = listening_rooms
        self._commands = commands
        self._conversation = conversation

        self._callbacks = None
        self._listening_room_ids = None

        # We have to fetch the aliases for every room to make sure we don't
        # join it twice by accident. However, fetching aliases is costly,
        # so we only do it once per room.
        self._aliases_fetched_for = {}

        # Word commands are stored dict-of-dict: First dict indexes by room ID
        #  / alias, second dict indexes by the word
        self._word_commands = {}

        # Regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list
        self._expression_commands = {}

        # Configuration options for the AsyncClient
        _client_config = AsyncClientConfig(
            max_limit_exceeded=0,
            max_timeouts=0,
            store_sync_tokens=True,
            encryption_enabled=False,
        )

        # Initialize the matrix client
        self._client = AsyncClient(
            self._homeserver,
            self._mx_id,
            device_id=self._device_id,
            store_path=self._session_filepath + "_session",
            config=_client_config,
        )

    async def get_listening_room_ids(self):
        """Return the room ids of the rooms the bot have to listen.

        Returns:
          A list of the room ids where the bot should listen.
        """

        if self._listening_room_ids:
            return self._listening_room_ids
        self._listening_room_ids = []
        for _room_id_or_alias in self._listening_rooms:
            self._listening_room_ids.append(
                await self.resolve_room_id(_room_id_or_alias)
            )
        return self._listening_room_ids

    async def compute_commands(self):
        """Set up the variables for a different kind of command types."""

        async def _set_word_command(_room_id, _command):
            """Set the word commands."""

            _room_id = await self.resolve_room_id(_room_id)
            if _room_id in self._conversation[CONF_ROOMS]:
                return

            if _room_id not in self._word_commands:
                self._word_commands[_room_id] = {}

            if len(_command[CONF_ROOMS]) > 0:
                _room_id_list = []
                for _room_id_or_alias in _command[CONF_ROOMS]:
                    _id = await self.resolve_room_id(_room_id_or_alias)
                    if _id not in self._conversation[CONF_ROOMS]:
                        _room_id_list.append(_id)
                _command[CONF_ROOMS] = list(_room_id_list)

            _LOGGER.debug("Word command: %s", str(_command))
            self._word_commands[_room_id][_command[CONF_WORD]] = _command

        async def _set_expression_command(_room_id, _command):
            """Set the expression commands."""

            _room_id = await self.resolve_room_id(_room_id)
            if (
                self._conversation[CONF_ROOMS]
                and _room_id in self._conversation[CONF_ROOMS]
            ):
                return

            if _room_id not in self._expression_commands:
                self._expression_commands[_room_id] = []

            if len(_command[CONF_ROOMS]) > 0:
                _room_id_list = []
                for _room_id_or_alias in _command[CONF_ROOMS]:
                    _id = await self.resolve_room_id(_room_id_or_alias)
                    if _id not in self._conversation[CONF_ROOMS]:
                        _room_id_list.append(_id)
                _command[CONF_ROOMS] = list(_room_id_list)

            _LOGGER.debug("Exp. command: %s", str(_command))
            self._expression_commands[_room_id].append(_command)

        # Compute the rooms the bot listens and sends everything to conversation
        if self._conversation:
            _LOGGER.debug("There is Conversation defined.")
            if self._conversation.get(CONF_ROOMS):
                _room_ids = []
                for _room_id_or_alias in self._conversation[CONF_ROOMS]:
                    _room_ids.append(await self.resolve_room_id(_room_id_or_alias))
                self._conversation[CONF_ROOMS] = _room_ids

        _LOGGER.debug("Conversation: %s", str(self._conversation))
        # Compute the rooms the bot should listen for particular expressions
        for _command in self._commands:
            if not _command.get(CONF_ROOMS):
                for _room_id in await self.get_listening_room_ids():
                    if (
                        self._conversation
                        and _room_id not in self._conversation[CONF_ROOMS]
                    ):
                        _command[CONF_ROOMS].append(_room_id)

            if _command.get(CONF_WORD):
                for _room_id in _command[CONF_ROOMS]:
                    await _set_word_command(_room_id, _command)

            else:
                for _room_id in _command[CONF_ROOMS]:
                    await _set_expression_command(_room_id, _command)

        _LOGGER.debug("Word commands: %s", str(self._word_commands))
        _LOGGER.debug("Expression commands: %s", str(self._expression_commands))
        _LOGGER.debug("Conversation rooms: %s", str(self._conversation))

    async def get_commands(self):
        """Get the defined commands for the Callbacks.

        Returns:
          A dict with the commands for different kinds for
          a callback.
        """
        return dict(
            word_commands=self._word_commands,
            expression_commands=self._expression_commands,
            conversation=self._conversation[CONF_ROOMS],
        )

    async def login(self):
        """Login to Matrix."""
        _LOGGER.debug("Login with %s", self._mx_id)
        login_response = await self._client.login(
            password=self._password,
            device_name=self._device_id,
        )

        # Check if login failed
        if isinstance(login_response, LoginError):
            _LOGGER.error("Failed to login: %s", login_response.message)
            raise ProtocolError

    async def join_all_rooms(self):
        """Join all rooms if not already joined."""
        _LOGGER.debug("Join all rooms if not already joined.")

        for _room in self._listening_rooms:
            _room_id = await self.resolve_room_id(_room)
            await self.join_room_if_not_in(_room_id)

    async def startup_and_listen(self):
        """Initialize the bot."""

        await self.sync()
        await self.join_all_rooms()
        await self.sync()
        await self.compute_commands()
        await self.listen()

    async def listen(self):
        """Make Matrix client listening for events in rooms."""
        _LOGGER.debug("Add callbacks.")
        self._callbacks = Callbacks(self.hass, self._client, await self.get_commands())
        self._client.add_event_callback(self._callbacks.message, (RoomMessageText,))
        _LOGGER.debug("Listening forever on Matrix rooms...")

        while True:
            try:
                await self._client.sync_forever(timeout=30000, full_state=True)
            except ProtocolError as exception:
                _LOGGER.warning(
                    "Unable to connect to homeserver (%s), retrying in 15s...",
                    str(exception),
                )

                # Sleep so we don't bombard the server with login requests
                sleep(15)
            finally:
                await self._client.close()

    async def close(self, junk):
        """Close the client connection."""
        _LOGGER.debug("Matrix connection closed.")
        await self._client.close()

    async def sync(self):
        """Sync the state."""
        _LOGGER.debug("Syncing...")
        await self._client.sync()
        _LOGGER.debug("Syncing... Done.")

    async def handle_send_message(self, service):
        """Handle the send messages to the rooms."""
        _LOGGER.debug("Sending message to %s", str(service.data[ATTR_TARGET]))

        for _room_id_or_alias in service.data[ATTR_TARGET]:
            _room_id = await self.resolve_room_id(_room_id_or_alias)

            if _room_id:
                await self.join_room_if_not_in(_room_id)
                await self.send_text_to_room(
                    _room_id,
                    service.data[ATTR_MESSAGE],
                    markdown_convert=service.data[ATTR_MARKDOWN],
                    notice=service.data[ATTR_NOTICE],
                )

    async def handle_send_image(self, service):
        """Handle the send image to the rooms."""
        _LOGGER.debug("Sending image to %s", str(service.data[ATTR_TARGET]))

        if ATTR_URL in service.data:
            _file_path = NamedTemporaryFile(delete=False).name
            async with aiohttp.ClientSession() as session:
                async with session.get(service.data[ATTR_URL]) as _resp:
                    if _resp.status == 200:
                        file_object = await aiofiles.open(_file_path, mode="wb")
                        await file_object.write(await _resp.read())
                        await file_object.close()
                    else:
                        _LOGGER.warning(
                            "Downloading the url %s failed with response code: %s",
                            str(service.data[ATTR_URL]),
                            str(_resp.status),
                        )
                        return

        else:
            _file_path = service.data[ATTR_FILE]
        _room_ids = []

        for _room_id_or_alias in service.data[ATTR_TARGET]:
            _room_id = await self.resolve_room_id(_room_id_or_alias)

            if _room_id:
                _room_ids.append(_room_id)
                await self.join_room_if_not_in(_room_id)

        await self.send_image_to_rooms(_room_ids, _file_path)
        if ATTR_URL in service.data:
            try:
                os.unlink(_file_path)
            except OSError as exception:
                _LOGGER.warning(
                    "The deletion of %s failed. (%s)", str(_file_path), str(exception)
                )

    async def resolve_room_id(self, room_id_or_alias):
        """Resolve the room id if we put in a room alias.

        Returns:
          Returns the room id for the alias/id or
          False if there is no match
        """

        if room_id_or_alias.startswith("#"):
            # This is an alias (first character is #)
            if room_id_or_alias in self._aliases_fetched_for.keys():
                _LOGGER.debug("Room ID fetched from cache.")
                return self._aliases_fetched_for[room_id_or_alias]

            _LOGGER.debug("Resolv room id from room alias: %s", room_id_or_alias)
            room_id = await self._client.room_resolve_alias(room_id_or_alias)

            if not isinstance(room_id, RoomResolveAliasResponse):
                _LOGGER.error("The room id can't be found: %s", str(room_id))
                return False

            room_id = room_id.room_id
            self._aliases_fetched_for[room_id_or_alias] = room_id
            _LOGGER.debug("The resolved room id is: %s", str(room_id))

        elif room_id_or_alias.startswith("!"):
            # This is a room id (first character is !)
            room_id = room_id_or_alias

        else:
            _LOGGER.error(
                "This doesn't look like a valid room id or alias: %s",
                str(room_id_or_alias),
            )
            return False

        return room_id

    async def join_room_if_not_in(self, room_id):
        """Join rooms.

        If the bot is not in the room already, then
        join the bot in the room.
        """

        _joined_rooms = await self._client.joined_rooms()
        _LOGGER.debug("Joined rooms: %s", str(_joined_rooms.rooms))

        if room_id not in _joined_rooms.rooms:
            _LOGGER.debug("Joining to room: %s", str(room_id))
            _response = await self._client.join(room_id)

            if not isinstance(_response, JoinResponse):
                _LOGGER.error("Unable to join to the room: %s", str(_response))
                return False
            _LOGGER.debug("Joined into the room: %s", str(room_id))

    async def send_text_to_room(
        self,
        room_id: str,
        message: str,
        markdown_convert: bool = False,
        notice: bool = False,
        reply_to_event_id: str = None,
    ):
        """Send text to a matrix room.

        Args:
            client: The client to communicate to matrix with.
            room_id: The ID of the room to send the message to.
            message: The message content.
            markdown_convert: Whether to convert the message content to markdown.
                Defaults to true.
            notice: Whether the message should be sent with an "m.notice" message type
                (will not ping users).
            reply_to_event_id: Whether this message is a reply to another event. The event
                ID this is message is a reply to.
        Returns:
            A RoomSendResponse if the request was successful, else an ErrorResponse.
        """

        _LOGGER.debug("Send message to %s", room_id)
        # Determine whether to ping room members or not
        _msgtype = "m.notice" if notice else "m.text"

        _content = {
            "msgtype": _msgtype,
            "format": "org.matrix.custom.html",
            "body": message,
        }

        if markdown_convert:
            _content["formatted_body"] = markdown(message)

        if reply_to_event_id:
            _content["m.relates_to"] = {
                "m.in_reply_to": {"event_id": reply_to_event_id}
            }

        try:
            _response = await self._client.room_send(
                room_id,
                "m.room.message",
                _content,
                ignore_unverified_devices=True,
            )
            if not isinstance(_response, RoomSendResponse):
                _LOGGER.error("Unable to send message response: %s", str(_response))
                return False
            _LOGGER.debug("Response: %s", str(_response))
        except SendRetryError:
            _LOGGER.error("Unable to send message response to %s", str(room_id))

    async def send_image_to_rooms(self, room_ids, image):
        """Process image.

        Arguments:
        ---------
        room_id : list of room_ids
        image : str
            file name of image from --image argument
        caption : str of the caption text
        This is a working example for a JPG image.
        It can be viewed or downloaded from:
        https://matrix.example.com/_matrix/media/r0/download/
            example.com/SomeStrangeUriKey
        {
            "type": "m.room.message",
            "sender": "@someuser:example.com",
            "content": {
                "body": "someimage.jpg",
                "info": {
                    "size": 5420,
                    "mimetype": "image/jpeg",
                    "thumbnail_info": {
                        "w": 100,
                        "h": 100,
                        "mimetype": "image/jpeg",
                        "size": 2106
                    },
                    "w": 100,
                    "h": 100,
                    "thumbnail_url": "mxc://example.com/SomeStrangeThumbnailUriKey"
                },
                "msgtype": "m.image",
                "url": "mxc://example.com/SomeStrangeUriKey"
            },
            "origin_server_ts": 12345678901234576,
            "unsigned": {
                "age": 268
            },
            "event_id": "$skdhGJKhgyr548654YTr765Yiy58TYR",
            "room_id": "!JKHgyHGfytHGFjhgfY:example.com"
        }
        """
        if not room_ids:
            _LOGGER.warning(
                "No rooms are given. This should not happen. This image is being dropped and NOT sent."
            )
            return
        if not os.path.isfile(image):
            _LOGGER.warning(
                "Image file %s is not a file. Doesn't exist or "
                "is a directory."
                "This image is being dropped and NOT sent.",
                str(image),
            )
            return

        # 'application/pdf' "image/jpeg"
        mime_type = magic.from_file(image, mime=True)
        if not mime_type.startswith("image/"):
            _LOGGER.warning(
                "Image file %s does not have an image mime type. "
                "Should be something like image/jpeg. "
                "Found mime type %s. "
                "This image is being dropped and NOT sent.",
                str(image),
                str(mime_type),
            )
            return

        image_object = Image.open(image)
        (
            width,
            height,
        ) = image_object.size  # image_object.size returns (width,height) tuple

        # first do an upload of image, see upload() documentation
        # http://matrix-nio.readthedocs.io/en/latest/nio.html#nio.AsyncClient.upload
        # then send URI of upload to room

        file_stat = await aiofiles.os.stat(image)
        async with aiofiles.open(image, "r+b") as file_object:
            resp, maybe_keys = await self._client.upload(
                file_object,
                content_type=mime_type,  # image/jpeg
                filename=os.path.basename(image),
                filesize=file_stat.st_size,
            )
        del maybe_keys
        if isinstance(resp, UploadResponse):
            _LOGGER.debug(
                "Image was uploaded successfully to server. " "Response is: %s",
                str(resp),
            )
        else:
            _LOGGER.warning(
                "The bot failed to upload. "
                "Please retry. This could be temporary issue on "
                "your server. "
                "Sorry."
            )
            _LOGGER.warning(
                'file="%s"; mime_type="%s"; ' 'filessize="%s"' "Failed to upload: %s",
                str(image),
                str(mime_type),
                str(file_stat.st_size),
                str(repr),
            )

        content = {
            "body": os.path.basename(image),  # descriptive title
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "thumbnail_info": None,
                "w": width,  # width in pixel
                "h": height,  # height in pixel
                "thumbnail_url": None,
            },
            "msgtype": "m.image",
            "url": resp.content_uri,
        }

        for _room_id in room_ids:
            try:
                await self._client.room_send(
                    _room_id, message_type="m.room.message", content=content
                )
                _LOGGER.debug(
                    'This image file was sent: "%s" to room "%s".',
                    str(image),
                    str(_room_id),
                )
            except ProtocolError as exception:
                _LOGGER.warning(
                    "Image send of file %s failed. Sorry. (%s)",
                    str(image),
                    str(exception),
                )


class Callbacks:
    """Callbacks to handle messages from the room."""

    def __init__(self, hass, client: AsyncClient, commands):
        """
        Callbacks to handle messages from the room.

        Args:
            client: nio client used to interact with matrix.
        """
        _LOGGER.debug("Matrix Callbacks Class.")
        self.hass = hass
        self._client = client
        self._expression_commands = commands["expression_commands"]
        self._word_commands = commands["word_commands"]
        self._conversation = commands["conversation"]

    async def message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """
        Message event Callback.

        Args:
            room: The room the event came from.
            event: The event.
        """

        # Extract the message text
        _msg = event.body
        _room_id = room.room_id
        _LOGGER.debug("Received a message: %s in room: %s", str(_msg), str(_room_id))
        # Ignore messages from ourselves
        if event.sender == self._client.user:
            return

        if _room_id in self._conversation:
            # This message need to be delivered to conversation service
            _LOGGER.debug("Type conversation.")
            _response = await self.hass.services.async_call(
                "conversation", "process", service_data=dict(text=_msg), blocking=True
            )
            _LOGGER.debug("Response: %s", str(_response))
            return

        if _msg[0] == "!":
            # Could trigger a single-word command
            _LOGGER.debug("Type word: %s", str(_msg))
            pieces = _msg.split(" ")
            cmd = pieces[0][1:]

            command = self._word_commands.get(_room_id, {}).get(cmd)
            if command:
                event_data = {
                    "command": command[CONF_NAME],
                    "sender": event.sender,
                    "room": _room_id,
                    "args": pieces[1:],
                }
                self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room
        for command in self._expression_commands.get(_room_id, []):
            _LOGGER.debug("Type expression: %s", str(command[CONF_NAME]))
            match = command[CONF_EXPRESSION].match(_msg)
            if not match:
                continue
            event_data = {
                "command": command[CONF_NAME],
                "sender": event.sender,
                "room": _room_id,
                "args": match.groupdict(),
            }
            self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)
