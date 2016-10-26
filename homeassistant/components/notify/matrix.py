"""
Matrix notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.matrix/
"""
import logging
import json
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL

REQUIREMENTS = ['matrix-client==0.0.5']

SESSION_FILE = 'matrix.conf'
AUTH_TOKENS = dict()

CONF_HOMESERVER = 'homeserver'
CONF_DEFAULT_ROOM = 'default_room'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOMESERVER): cv.url,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_DEFAULT_ROOM): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the Matrix notification service."""
    if not AUTH_TOKENS:
        load_token(hass.config.path(SESSION_FILE))

    return MatrixNotificationService(
        config.get(CONF_HOMESERVER),
        config.get(CONF_DEFAULT_ROOM),
        config.get(CONF_VERIFY_SSL),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD)
    )


# pylint: disable=too-few-public-methods
class MatrixNotificationService(BaseNotificationService):
    """Wrapper for the MatrixNotificationClient."""

    # pylint: disable=too-many-arguments
    def __init__(self, homeserver, default_room, verify_ssl,
                 username, password):
        """Buffer configuration data for send_message."""
        self.homeserver = homeserver
        self.default_room = default_room
        self.verify_tls = verify_ssl
        self.username = username
        self.password = password

    def send_message(self, message, **kwargs):
        """Wrapper function pass default parameters to actual send_message."""
        send_message(
            message,
            self.homeserver,
            kwargs.get(ATTR_TARGET) or [self.default_room],
            self.verify_tls,
            self.username,
            self.password
        )


def load_token(session_file):
    """Load authentication tokens from persistent storage, if exists."""
    if not os.path.exists(session_file):
        return

    with open(session_file) as handle:
        data = json.load(handle)

    for mx_id, token in data.items():
        AUTH_TOKENS[mx_id] = token


def store_token(mx_id, token):
    """Store authentication token to session and persistent storage."""
    AUTH_TOKENS[mx_id] = token

    with open(SESSION_FILE, 'w') as handle:
        handle.write(json.dumps(AUTH_TOKENS))


# pylint: disable=too-many-locals, too-many-arguments
def send_message(message, homeserver, target_rooms, verify_tls,
                 username, password):
    """Do everything thats necessary to send a message to a Matrix room."""
    from matrix_client.client import MatrixClient, MatrixRequestError

    def login_by_token():
        """Login using authentication token."""
        try:
            return MatrixClient(
                base_url=homeserver,
                token=AUTH_TOKENS[mx_id],
                user_id=username,
                valid_cert_check=verify_tls
            )
        except MatrixRequestError as ex:
            _LOGGER.info(
                'login_by_token: (%d) %s', ex.code, ex.content
            )

    def login_by_password():
        """Login using password authentication."""
        try:
            _client = MatrixClient(
                base_url=homeserver,
                valid_cert_check=verify_tls
            )
            _client.login_with_password(username, password)
            store_token(mx_id, _client.token)
            return _client
        except MatrixRequestError as ex:
            _LOGGER.error(
                'login_by_password: (%d) %s', ex.code, ex.content
            )

    # this is as close as we can get to the mx_id, since there is no
    # homeserver discovery protocol we have to fall back to the homeserver url
    # instead of the actual domain it serves.
    mx_id = "{user}@{homeserver}".format(
        user=username,
        homeserver=homeserver
    )

    if mx_id in AUTH_TOKENS:
        client = login_by_token()
        if not client:
            client = login_by_password()
            if not client:
                _LOGGER.error(
                    'login failed, both token and username/password '
                    'invalid'
                )
                return
    else:
        client = login_by_password()
        if not client:
            _LOGGER.error('login failed, username/password invalid')
            return

    rooms = client.get_rooms()
    for target_room in target_rooms:
        try:
            if target_room in rooms:
                room = rooms[target_room]
            else:
                room = client.join_room(target_room)

            _LOGGER.debug(room.send_text(message))
        except MatrixRequestError as ex:
            _LOGGER.error(
                'Unable to deliver message to room \'%s\': (%d): %s',
                target_room, ex.code, ex.content
            )
