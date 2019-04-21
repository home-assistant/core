"""
Slack platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.slack/
"""
import logging

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_ICON, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (
    ATTR_DATA, ATTR_TARGET, ATTR_TITLE, PLATFORM_SCHEMA,
    BaseNotificationService)

REQUIREMENTS = ['slacker==0.12.0']

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL = 'default_channel'
CONF_TIMEOUT = 15

# Top level attributes in 'data'
ATTR_ATTACHMENTS = 'attachments'
ATTR_FILE = 'file'
# Attributes contained in file
ATTR_FILE_URL = 'url'
ATTR_FILE_PATH = 'path'
ATTR_FILE_USERNAME = 'username'
ATTR_FILE_PASSWORD = 'password'
ATTR_FILE_AUTH = 'auth'
# Any other value or absence of 'auth' lead to basic authentication being used
ATTR_FILE_AUTH_DIGEST = 'digest'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_CHANNEL): cv.string,
    vol.Optional(CONF_ICON): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Slack notification service."""
    import slacker

    channel = config.get(CONF_CHANNEL)
    api_key = config.get(CONF_API_KEY)
    username = config.get(CONF_USERNAME)
    icon = config.get(CONF_ICON)

    try:
        return SlackNotificationService(
            channel, api_key, username, icon, hass.config.is_allowed_path)

    except slacker.Error:
        _LOGGER.exception("Authentication failed")
        return None


class SlackNotificationService(BaseNotificationService):
    """Implement the notification service for Slack."""

    def __init__(
            self, default_channel, api_token, username, icon, is_allowed_path):
        """Initialize the service."""
        from slacker import Slacker
        self._default_channel = default_channel
        self._api_token = api_token
        self._username = username
        self._icon = icon
        if self._username or self._icon:
            self._as_user = False
        else:
            self._as_user = True

        self.is_allowed_path = is_allowed_path
        self.slack = Slacker(self._api_token)
        self.slack.auth.test()

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        import slacker

        if kwargs.get(ATTR_TARGET) is None:
            targets = [self._default_channel]
        else:
            targets = kwargs.get(ATTR_TARGET)

        data = kwargs.get(ATTR_DATA)
        attachments = data.get(ATTR_ATTACHMENTS) if data else None
        file = data.get(ATTR_FILE) if data else None
        title = kwargs.get(ATTR_TITLE)

        for target in targets:
            try:
                if file is not None:
                    # Load from file or URL
                    file_as_bytes = self.load_file(
                        url=file.get(ATTR_FILE_URL),
                        local_path=file.get(ATTR_FILE_PATH),
                        username=file.get(ATTR_FILE_USERNAME),
                        password=file.get(ATTR_FILE_PASSWORD),
                        auth=file.get(ATTR_FILE_AUTH))
                    # Choose filename
                    if file.get(ATTR_FILE_URL):
                        filename = file.get(ATTR_FILE_URL)
                    else:
                        filename = file.get(ATTR_FILE_PATH)
                    # Prepare structure for Slack API
                    data = {
                        'content': None,
                        'filetype': None,
                        'filename': filename,
                        # If optional title is none use the filename
                        'title': title if title else filename,
                        'initial_comment': message,
                        'channels': target
                    }
                    # Post to slack
                    self.slack.files.post(
                        'files.upload', data=data,
                        files={'file': file_as_bytes})
                else:
                    self.slack.chat.post_message(
                        target, message, as_user=self._as_user,
                        username=self._username, icon_emoji=self._icon,
                        attachments=attachments, link_names=True)
            except slacker.Error as err:
                _LOGGER.error("Could not send notification. Error: %s", err)

    def load_file(self, url=None, local_path=None, username=None,
                  password=None, auth=None):
        """Load image/document/etc from a local path or URL."""
        try:
            if url:
                # Check whether authentication parameters are provided
                if username:
                    # Use digest or basic authentication
                    if ATTR_FILE_AUTH_DIGEST == auth:
                        auth_ = HTTPDigestAuth(username, password)
                    else:
                        auth_ = HTTPBasicAuth(username, password)
                    # Load file from URL with authentication
                    req = requests.get(url, auth=auth_, timeout=CONF_TIMEOUT)
                else:
                    # Load file from URL without authentication
                    req = requests.get(url, timeout=CONF_TIMEOUT)
                return req.content

            if local_path:
                # Check whether path is whitelisted in configuration.yaml
                if self.is_allowed_path(local_path):
                    return open(local_path, 'rb')
                _LOGGER.warning(
                    "'%s' is not secure to load data from!", local_path)
            else:
                _LOGGER.warning("Neither URL nor local path found in params!")

        except OSError as error:
            _LOGGER.error("Can't load from URL or local path: %s", error)

        return None
