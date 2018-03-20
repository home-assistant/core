"""
The matrix bot component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/matrix/
"""
import logging
import os
from urllib.parse import urlparse

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, ATTR_MESSAGE)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['matrix-client==0.0.6']

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = 'matrix.conf'

CONF_HOMESERVER = 'homeserver'
CONF_LISTENING_ROOMS = 'listening_rooms'
CONF_COMMANDS = 'commands'

EVENT_MATRIX_COMMAND = 'matrix_command'

DOMAIN = 'matrix'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_HOMESERVER): cv.url,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_LISTENING_ROOMS, default=[]): vol.All(cv.ensure_list,
                                                            [cv.string]),
    vol.Optional(CONF_COMMANDS, default=[]): vol.All(cv.ensure_list,
                                                     [cv.string]),
})

SERVICE_SEND_MESSAGE = 'send_message'

SERVICE_SCHEMA_SEND_MESSAGE = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
})


def setup(hass, config):
    """Set up the Matrix bot component."""
    if not config[DOMAIN]:
        return False

    config = config[DOMAIN][0]

    bot = MatrixBot(
        hass,
        os.path.join(hass.config.path(), SESSION_FILE),
        config.get(CONF_HOMESERVER),
        config.get(CONF_VERIFY_SSL),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_LISTENING_ROOMS, []),
        config.get(CONF_COMMANDS, []))
    hass.data[DOMAIN] = bot

    def send_message_handler(service):
        """Handle the send_message service."""
        bot.handle_send_message(service)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, send_message_handler,
        schema=SERVICE_SCHEMA_SEND_MESSAGE)

    return True


class MatrixBot(object):
    """The Matrix Bot."""

    def __init__(self, hass, config_file, homeserver, verify_ssl,
                 username, password, listening_rooms, commands):
        """Set up the client."""
        self.hass = hass

        self._session_filepath = config_file
        self._auth_tokens = self._get_auth_tokens()

        self._homeserver = homeserver
        self._verify_tls = verify_ssl
        self._username = username
        self._password = password

        self._mx_id = "{user}@{homeserver}".format(
            user=username, homeserver=urlparse(homeserver).netloc)

        self._listening_rooms = listening_rooms
        self._commands = set(commands)

        # Login, this will raise a MatrixRequestError if login is unsuccessful
        self._client = self._login()

        # Join rooms in which we listen for commands and start listening
        self._join_rooms()
        self._client.start_listener_thread()

    def _join_rooms(self):
        """ Join the rooms that we listen for commands in. """
        from matrix_client.client import MatrixRequestError

        def room_message_cb(room, event):
            """Handle a message sent to a room."""
            if (event['content']['msgtype'] == "m.text" and
                    event['content']['body'][0] == "!"):
                pieces = event['content']['body'].split(' ')
                cmd = pieces[0][1:]
                if cmd not in self._commands:
                    return

                event_data = {
                    'command': cmd,
                    'sender': event['sender'],
                    'room': room.room_id,
                    'args': pieces[1:]
                }

                self.hass.bus.fire(EVENT_MATRIX_COMMAND, event_data)

        joined_rooms = self._client.get_rooms()

        for room_id in self._listening_rooms:
            try:
                if room_id in joined_rooms:
                    room = joined_rooms[room_id]
                    _LOGGER.debug("Already in room {}".format(room_id))
                else:
                    room = self._client.join_room(room_id)
                    _LOGGER.debug("Joined room {}".format(room_id))

                room.add_listener(room_message_cb, "m.room.message")
            except MatrixRequestError as ex:
                _LOGGER.error("Could not join room {}: {}".format(room_id, ex))

    def _get_auth_tokens(self):
        """
        Read sorted authentication tokens from disk.

        Returns the auth_tokens dictionary.
        """
        if not os.path.exists(self._session_filepath):
            return {}

        try:
            data = load_json(self._session_filepath)

            auth_tokens = {}
            for mx_id, token in data.items():
                auth_tokens[mx_id] = token

            return auth_tokens

        except (OSError, IOError, PermissionError) as ex:
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

                # re-raise the error so the constructor can catch it.
                raise

        return client

    def _login_by_token(self):
        """Login using authentication token and return the client."""
        from matrix_client.client import MatrixClient

        return MatrixClient(
            base_url=self._homeserver,
            token=self._auth_tokens[self._mx_id],
            user_id=self._username,
            valid_cert_check=self._verify_tls)

    def _login_by_password(self):
        """Login using password authentication and return the client."""
        from matrix_client.client import MatrixClient

        _client = MatrixClient(
            base_url=self._homeserver,
            valid_cert_check=self._verify_tls)

        _client.login_with_password(self._username, self._password)

        self._store_auth_token(_client.token)

        return _client

    def _send_message(self, message, target_rooms):
        """Send the message to the matrix server."""
        from matrix_client.client import MatrixRequestError

        rooms = self._client.get_rooms()
        for target_room in target_rooms:
            try:
                if target_room in rooms:
                    room = rooms[target_room]
                else:
                    room = self._client.join_room(target_room)

                _LOGGER.debug(room.send_text(message))

            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room '%s': (%d): %s",
                    target_room, ex.code, ex.content)

    def handle_send_message(self, service):
        """Handle the send_message service."""
        self._send_message(service.data[ATTR_MESSAGE],
                           service.data[ATTR_TARGET])
