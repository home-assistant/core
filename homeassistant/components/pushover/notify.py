"""Pushover platform for notify component."""
import logging

from pushover import Client, InitError, RequestError
import requests
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

CONF_USER_KEY = "user_key"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USER_KEY): cv.string, vol.Required(CONF_API_KEY): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the Pushover notification service."""
    try:
        return PushoverNotificationService(
            hass, config[CONF_USER_KEY], config[CONF_API_KEY]
        )
    except InitError:
        _LOGGER.error("Wrong API key supplied")
        return None


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(self, hass, user_key, api_token):
        """Initialize the service."""
        self._hass = hass
        self._user_key = user_key
        self._api_token = api_token
        self.pushover = Client(self._user_key, api_token=self._api_token)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        # Make a copy and use empty dict if necessary
        data = dict(kwargs.get(ATTR_DATA) or {})

        data["title"] = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        # Check for attachment.
        if ATTR_ATTACHMENT in data:
            # If attachment is a URL, use requests to open it as a stream.
            if data[ATTR_ATTACHMENT].startswith("http"):
                try:
                    response = requests.get(
                        data[ATTR_ATTACHMENT], stream=True, timeout=5
                    )
                    if response.status_code == 200:
                        # Replace the attachment identifier with file object.
                        data[ATTR_ATTACHMENT] = response.content
                    else:
                        _LOGGER.error(
                            "Failed to download image %s, response code: %d",
                            data[ATTR_ATTACHMENT],
                            response.status_code,
                        )
                        # Remove attachment key to send without attachment.
                        del data[ATTR_ATTACHMENT]
                except requests.exceptions.RequestException as ex_val:
                    _LOGGER.error(ex_val)
                    # Remove attachment key to try sending without attachment
                    del data[ATTR_ATTACHMENT]
            else:
                # Not a URL, check valid path first
                if self._hass.config.is_allowed_path(data[ATTR_ATTACHMENT]):
                    # try to open it as a normal file.
                    try:
                        file_handle = open(data[ATTR_ATTACHMENT], "rb")
                        # Replace the attachment identifier with file object.
                        data[ATTR_ATTACHMENT] = file_handle
                    except OSError as ex_val:
                        _LOGGER.error(ex_val)
                        # Remove attachment key to send without attachment.
                        del data[ATTR_ATTACHMENT]
                else:
                    _LOGGER.error("Path is not whitelisted")
                    # Remove attachment key to send without attachment.
                    del data[ATTR_ATTACHMENT]

        targets = kwargs.get(ATTR_TARGET)

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            if target is not None:
                data["device"] = target

            try:
                self.pushover.send_message(message, **data)
            except ValueError as val_err:
                _LOGGER.error(val_err)
            except RequestError:
                _LOGGER.exception("Could not send pushover notification")
