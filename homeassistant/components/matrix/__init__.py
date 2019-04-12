"""The matrix bot component."""
import logging
import os
from functools import partial

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, ATTR_MESSAGE)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 CONF_VERIFY_SSL, CONF_NAME,
                                 EVENT_HOMEASSISTANT_STOP,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.util.json import load_json, save_json
from homeassistant.exceptions import HomeAssistantError

REQUIREMENTS = ['matrix-client==0.2.0']

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = '.matrix.conf'

CONF_HOMESERVER = 'homeserver'
CONF_ROOMS = 'rooms'
CONF_COMMANDS = 'commands'
CONF_WORD = 'word'
CONF_EXPRESSION = 'expression'

EVENT_MATRIX_COMMAND = 'matrix_command'

DOMAIN = 'matrix'

COMMAND_SCHEMA = vol.All(
    # Basic Schema
    vol.Schema({
        vol.Exclusive(CONF_WORD, 'trigger'): cv.string,
        vol.Exclusive(CONF_EXPRESSION, 'trigger'): cv.is_regex,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_ROOMS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
    # Make sure it's either a word or an expression command
    cv.has_at_least_one_key(CONF_WORD, CONF_EXPRESSION)
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOMESERVER): cv.url,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Required(CONF_USERNAME): cv.matches_regex("@[^:]*:.*"),
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_ROOMS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_COMMANDS, default=[]): [COMMAND_SCHEMA]
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_SEND_MESSAGE = 'send_message'

SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
})


def setup(hass, config):
    """Set up the Matrix bot component."""
    from matrix_client.client import MatrixRequestError

    config = config[DOMAIN]

    try:
        bot = MatrixBot(
            hass, os.path.join(hass.config.path(), SESSION_FILE),
            config[CONF_HOMESERVER], config[CONF_VERIFY_SSL],
            config[CONF_USERNAME], config[CONF_PASSWORD], config[CONF_ROOMS],
            config[CONF_COMMANDS])
        hass.data[DOMAIN] = bot
    except MatrixRequestError as exception:
        _LOGGER.error("Matrix failed to log in: %s", str(exception))
        return False

    hass.services.register(
        DOMAIN, SERVICE_SEND_MESSAGE, bot.handle_send_message,
        schema=SERVICE_SCHEMA_SEND_MESSAGE)

    return True


class MatrixBot:
    """The Matrix Bot."""

    def __init__(self, hass, config_file, homeserver, verify_ssl,
                 username, password, listening_rooms, commands):
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
        self._aliases_fetched_for = set()

        # word commands are stored dict-of-dict: First dict indexes by room ID
        #  / alias, second dict indexes by the word
        self._word_commands = {}

        # regular expression commands are stored as a list of commands per
        # room, i.e., a dict-of-list
        self._expression_commands = {}

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

        # Log in. This raises a MatrixRequestError if login is unsuccessful
        self._client = self._login()

        def handle_matrix_exception(exception):
            """Handle exceptions raised inside the Matrix SDK."""
            _LOGGER.error("Matrix exception:\n %s", str(exception))

        self._client.start_listener_thread(
            exception_handler=handle_matrix_exception)

        def stop_client(_):
            """Run once when Home Assistant stops."""
            self._client.stop_listener_thread()

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        # Joining rooms potentially does a lot of I/O, so we defer it
        def handle_startup(_):
            """Run once when Home Assistant finished startup."""
            self._join_rooms()

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_START, handle_startup)

    def _handle_room_message(self, room_id, room, event):
        """Handle a message sent to a room."""
        if event['content']['msgtype'] != 'm.text':
            return

        if event['sender'] == self._mx_id:
            return

        _LOGGER.debug("Handling message: %s", event['content']['body'])

        if event['content']['body'][0] == "!":
            # Could trigger a single-word command.
            pieces = event['content']['body'].split(' ')
            cmd = pieces[0][1:]

            command = self._word_commands.get(room_id, {}).get(cmd)
            if command:
                event_data = {
                    'command': command[CONF_NAME],
                    'sender': event['sender'],
                    'room': room_id,
                    'args': pieces[1:]
                }
                self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

        # After single-word commands, check all regex commands in the room
        for command in self._expression_commands.get(room_id, []):
            match = command[CONF_EXPRESSION].match(event['content']['body'])
            if not match:
                continue
            event_data = {
                'command': command[CONF_NAME],
                'sender': event['sender'],
                'room': room_id,
                'args': match.groupdict()
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
                _LOGGER.debug("Already in room %s (known as %s)",
                              room.room_id, room_id_or_alias)
                return room

        room = self._client.join_room(room_id_or_alias)
        _LOGGER.info("Joined room %s (known as %s)", room.room_id,
                     room_id_or_alias)
        return room

    def _join_rooms(self):
        """Join the rooms that we listen for commands in."""
        from matrix_client.client import MatrixRequestError

        for room_id in self._listening_rooms:
            try:
                room = self._join_or_get_room(room_id)
                room.add_listener(partial(self._handle_room_message, room_id),
                                  "m.room.message")

            except MatrixRequestError as ex:
                _LOGGER.error("Could not join room %s: %s", room_id, ex)

    def _get_auth_tokens(self):
        """
        Read sorted authentication tokens from disk.

        Returns the auth_tokens dictionary.
        """
        try:
            auth_tokens = load_json(self._session_filepath)

            return auth_tokens
        except HomeAssistantError as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self._session_filepath, str(ex))
            return {}

    def _store_auth_token(self, token):
        """Store authentication token to session and persistent storage."""
        self._auth_tokens[self._mx_id] = token

        save_json(self._session_filepath, self._auth_tokens)

    def _login(self):
        """Login to the matrix homeserver and return the client instance."""
        from matrix_client.client import MatrixRequestError

        # Attempt to generate a valid client using either of the two possible
        # login methods:
        client = None

        # If we have an authentication token
        if self._mx_id in self._auth_tokens:
            try:
                client = self._login_by_token()
                _LOGGER.debug("Logged in using stored token.")

            except MatrixRequestError as ex:
                _LOGGER.warning(
                    "Login by token failed, falling back to password. "
                    "login_by_token raised: (%d) %s",
                    ex.code, ex.content)

        # If we still don't have a client try password.
        if not client:
            try:
                client = self._login_by_password()
                _LOGGER.debug("Logged in using password.")

            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Login failed, both token and username/password invalid "
                    "login_by_password raised: (%d) %s",
                    ex.code, ex.content)

                # re-raise the error so _setup can catch it.
                raise

        return client

    def _login_by_token(self):
        """Login using authentication token and return the client."""
        from matrix_client.client import MatrixClient

        return MatrixClient(
            base_url=self._homeserver,
            token=self._auth_tokens[self._mx_id],
            user_id=self._mx_id,
            valid_cert_check=self._verify_tls)

    def _login_by_password(self):
        """Login using password authentication and return the client."""
        from matrix_client.client import MatrixClient

        _client = MatrixClient(
            base_url=self._homeserver,
            valid_cert_check=self._verify_tls)

        _client.login_with_password(self._mx_id, self._password)

        self._store_auth_token(_client.token)

        return _client

    def _send_message(self, message, target_rooms):
        """Send the message to the matrix server."""
        from matrix_client.client import MatrixRequestError

        for target_room in target_rooms:
            try:
                room = self._join_or_get_room(target_room)
                _LOGGER.debug(room.send_text(message))
            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room '%s': (%d): %s",
                    target_room, ex.code, ex.content)

    def handle_send_message(self, service):
        """Handle the send_message service."""
        self._send_message(service.data[ATTR_MESSAGE],
                           service.data[ATTR_TARGET])
