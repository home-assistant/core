"""Pushover platform for notify component."""
import logging

from pushover_complete import PushoverAPI
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_ATTACHMENT = "attachment"
ATTR_URL = "url"
ATTR_URL_TITLE = "url_title"
ATTR_PRIORITY = "priority"
ATTR_RETRY = "retry"
ATTR_SOUND = "sound"
ATTR_HTML = "html"
ATTR_CALLBACK_URL = "callback_url"
ATTR_EXPIRE = "expire"
ATTR_TIMESTAMP = "timestamp"

CONF_USER_KEY = "user_key"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USER_KEY): cv.string, vol.Required(CONF_API_KEY): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the Pushover notification service."""
    return PushoverNotificationService(
        hass, config[CONF_USER_KEY], config[CONF_API_KEY]
    )


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(self, hass, user_key, api_token):
        """Initialize the service."""
        self._hass = hass
        self._user_key = user_key
        self._api_token = api_token
        self.pushover = PushoverAPI(self._api_token)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        # Extract params from data dict
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = dict(kwargs.get(ATTR_DATA) or {})
        url = data.get(ATTR_URL)
        url_title = data.get(ATTR_URL_TITLE)
        priority = data.get(ATTR_PRIORITY)
        retry = data.get(ATTR_RETRY)
        expire = data.get(ATTR_EXPIRE)
        callback_url = data.get(ATTR_CALLBACK_URL)
        timestamp = data.get(ATTR_TIMESTAMP)
        sound = data.get(ATTR_SOUND)
        html = 1 if data.get(ATTR_HTML, False) else 0

        image = data.get(ATTR_ATTACHMENT)
        # Check for attachment
        if image is not None:
            # Only allow attachments from whitelisted paths, check valid path
            if self._hass.config.is_allowed_path(data[ATTR_ATTACHMENT]):
                # try to open it as a normal file.
                try:
                    # pylint: disable=consider-using-with
                    file_handle = open(data[ATTR_ATTACHMENT], "rb")
                    # Replace the attachment identifier with file object.
                    image = file_handle
                except OSError as ex_val:
                    _LOGGER.error(ex_val)
                    # Remove attachment key to send without attachment.
                    image = None
            else:
                _LOGGER.error("Path is not whitelisted")
                # Remove attachment key to send without attachment.
                image = None

        targets = kwargs.get(ATTR_TARGET)

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            try:
                self.pushover.send_message(
                    self._user_key,
                    message,
                    target,
                    title,
                    url,
                    url_title,
                    image,
                    priority,
                    retry,
                    expire,
                    callback_url,
                    timestamp,
                    sound,
                    html,
                )
            except ValueError as val_err:
                _LOGGER.error(val_err)
