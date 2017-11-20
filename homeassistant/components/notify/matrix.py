"""
Matrix notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.matrix/
"""
import logging
import os
from urllib.parse import urlparse

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA,
                                             BaseNotificationService)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['matrix-client==0.0.6']

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = 'matrix.conf'

CONF_HOMESERVER = 'homeserver'
CONF_DEFAULT_ROOM = 'default_room'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOMESERVER): cv.url,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_DEFAULT_ROOM): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Matrix notification service."""
    from matrix_client.client import MatrixRequestError

    try:
        return MatrixNotificationService(
            os.path.join(hass.config.path(), SESSION_FILE),
            config.get(CONF_HOMESERVER),
            config.get(CONF_DEFAULT_ROOM),
            config.get(CONF_VERIFY_SSL),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD))

    except MatrixRequestError:
        return None


class MatrixNotificationService(BaseNotificationService):
    """Send Notifications to a Matrix Room."""

    def __init__(self, config_file, homeserver, default_room, verify_ssl,
                 username, password):
        """Set up the client."""
        self.session_filepath = config_file
        self.auth_tokens = self.get_auth_tokens()

        self.homeserver = homeserver
        self.default_room = default_room
        self.verify_tls = verify_ssl
        self.username = username
        self.password = password

        self.mx_id = "{user}@{homeserver}".format(
            user=username, homeserver=urlparse(homeserver).netloc)

        # Login, this will raise a MatrixRequestError if login is unsuccessful
        self.client = self.login()

    def get_auth_tokens(self):
        """
        Read sorted authentication tokens from disk.

        Returns the auth_tokens dictionary.
        """
        if not os.path.exists(self.session_filepath):
            return {}

        try:
            data = load_json(self.session_filepath)

            auth_tokens = {}
            for mx_id, token in data.items():
                auth_tokens[mx_id] = token

            return auth_tokens

        except (OSError, IOError, PermissionError) as ex:
            _LOGGER.warning(
                "Loading authentication tokens from file '%s' failed: %s",
                self.session_filepath, str(ex))
            return {}

    def store_auth_token(self, token):
        """Store authentication token to session and persistent storage."""
        self.auth_tokens[self.mx_id] = token

        save_json(self.session_filepath, self.auth_tokens)

    def login(self):
        """Login to the matrix homeserver and return the client instance."""
        from matrix_client.client import MatrixRequestError

        # Attempt to generate a valid client using either of the two possible
        # login methods:
        client = None

        # If we have an authentication token
        if self.mx_id in self.auth_tokens:
            try:
                client = self.login_by_token()
                _LOGGER.debug("Logged in using stored token.")

            except MatrixRequestError as ex:
                _LOGGER.warning(
                    "Login by token failed, falling back to password. "
                    "login_by_token raised: (%d) %s",
                    ex.code, ex.content)

        # If we still don't have a client try password.
        if not client:
            try:
                client = self.login_by_password()
                _LOGGER.debug("Logged in using password.")

            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Login failed, both token and username/password invalid "
                    "login_by_password raised: (%d) %s",
                    ex.code, ex.content)

                # re-raise the error so the constructor can catch it.
                raise

        return client

    def login_by_token(self):
        """Login using authentication token and return the client."""
        from matrix_client.client import MatrixClient

        return MatrixClient(
            base_url=self.homeserver,
            token=self.auth_tokens[self.mx_id],
            user_id=self.username,
            valid_cert_check=self.verify_tls)

    def login_by_password(self):
        """Login using password authentication and return the client."""
        from matrix_client.client import MatrixClient

        _client = MatrixClient(
            base_url=self.homeserver,
            valid_cert_check=self.verify_tls)

        _client.login_with_password(self.username, self.password)

        self.store_auth_token(_client.token)

        return _client

    def send_message(self, message, **kwargs):
        """Send the message to the matrix server."""
        from matrix_client.client import MatrixRequestError

        target_rooms = kwargs.get(ATTR_TARGET) or [self.default_room]

        rooms = self.client.get_rooms()
        for target_room in target_rooms:
            try:
                if target_room in rooms:
                    room = rooms[target_room]
                else:
                    room = self.client.join_room(target_room)

                _LOGGER.debug(room.send_text(message))

            except MatrixRequestError as ex:
                _LOGGER.error(
                    "Unable to deliver message to room '%s': (%d): %s",
                    target_room, ex.code, ex.content)
