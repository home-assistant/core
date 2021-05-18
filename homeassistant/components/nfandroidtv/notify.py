"""Notifications for Android TV notification service."""
import base64
import io
import logging

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST, CONF_TIMEOUT, HTTP_OK, PERCENTAGE
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_DURATION = "duration"
CONF_FONTSIZE = "fontsize"
CONF_POSITION = "position"
CONF_TRANSPARENCY = "transparency"
CONF_COLOR = "color"
CONF_INTERRUPT = "interrupt"

DEFAULT_DURATION = 5
DEFAULT_FONTSIZE = "medium"
DEFAULT_POSITION = "bottom-right"
DEFAULT_TRANSPARENCY = "default"
DEFAULT_COLOR = "grey"
DEFAULT_INTERRUPT = False
DEFAULT_TIMEOUT = 5
DEFAULT_ICON = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGP6zwAAAgcBApo"
    "cMXEAAAAASUVORK5CYII="
)

ATTR_DURATION = "duration"
ATTR_FONTSIZE = "fontsize"
ATTR_POSITION = "position"
ATTR_TRANSPARENCY = "transparency"
ATTR_COLOR = "color"
ATTR_BKGCOLOR = "bkgcolor"
ATTR_INTERRUPT = "interrupt"
ATTR_IMAGE = "filename2"
ATTR_FILE = "file"
# Attributes contained in file
ATTR_FILE_URL = "url"
ATTR_FILE_PATH = "path"
ATTR_FILE_USERNAME = "username"
ATTR_FILE_PASSWORD = "password"
ATTR_FILE_AUTH = "auth"
# Any other value or absence of 'auth' lead to basic authentication being used
ATTR_FILE_AUTH_DIGEST = "digest"

FONTSIZES = {"small": 1, "medium": 0, "large": 2, "max": 3}

POSITIONS = {
    "bottom-right": 0,
    "bottom-left": 1,
    "top-right": 2,
    "top-left": 3,
    "center": 4,
}

TRANSPARENCIES = {
    "default": 0,
    f"0{PERCENTAGE}": 1,
    f"25{PERCENTAGE}": 2,
    f"50{PERCENTAGE}": 3,
    f"75{PERCENTAGE}": 4,
    f"100{PERCENTAGE}": 5,
}

COLORS = {
    "grey": "#607d8b",
    "black": "#000000",
    "indigo": "#303F9F",
    "green": "#4CAF50",
    "red": "#F44336",
    "cyan": "#00BCD4",
    "teal": "#009688",
    "amber": "#FFC107",
    "pink": "#E91E63",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.Coerce(int),
        vol.Optional(CONF_FONTSIZE, default=DEFAULT_FONTSIZE): vol.In(FONTSIZES.keys()),
        vol.Optional(CONF_POSITION, default=DEFAULT_POSITION): vol.In(POSITIONS.keys()),
        vol.Optional(CONF_TRANSPARENCY, default=DEFAULT_TRANSPARENCY): vol.In(
            TRANSPARENCIES.keys()
        ),
        vol.Optional(CONF_COLOR, default=DEFAULT_COLOR): vol.In(COLORS.keys()),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
        vol.Optional(CONF_INTERRUPT, default=DEFAULT_INTERRUPT): cv.boolean,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the Notifications for Android TV notification service."""
    remoteip = config.get(CONF_HOST)
    duration = config.get(CONF_DURATION)
    fontsize = config.get(CONF_FONTSIZE)
    position = config.get(CONF_POSITION)
    transparency = config.get(CONF_TRANSPARENCY)
    color = config.get(CONF_COLOR)
    interrupt = config.get(CONF_INTERRUPT)
    timeout = config.get(CONF_TIMEOUT)

    return NFAndroidTVNotificationService(
        remoteip,
        duration,
        fontsize,
        position,
        transparency,
        color,
        interrupt,
        timeout,
        hass.config.is_allowed_path,
    )


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(
        self,
        remoteip,
        duration,
        fontsize,
        position,
        transparency,
        color,
        interrupt,
        timeout,
        is_allowed_path,
    ):
        """Initialize the service."""
        self._target = f"http://{remoteip}:7676"
        self._default_duration = duration
        self._default_fontsize = fontsize
        self._default_position = position
        self._default_transparency = transparency
        self._default_color = color
        self._default_interrupt = interrupt
        self._timeout = timeout
        self._icon_file = io.BytesIO(base64.b64decode(DEFAULT_ICON))
        self.is_allowed_path = is_allowed_path

    def send_message(self, message="", **kwargs):
        """Send a message to a Android TV device."""
        _LOGGER.debug("Sending notification to: %s", self._target)

        payload = {
            "filename": (
                "icon.png",
                self._icon_file,
                "application/octet-stream",
                {"Expires": "0"},
            ),
            "type": "0",
            "title": kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            "msg": message,
            "duration": "%i" % self._default_duration,
            "fontsize": "%i" % FONTSIZES.get(self._default_fontsize),
            "position": "%i" % POSITIONS.get(self._default_position),
            "bkgcolor": "%s" % COLORS.get(self._default_color),
            "transparency": "%i" % TRANSPARENCIES.get(self._default_transparency),
            "offset": "0",
            "app": ATTR_TITLE_DEFAULT,
            "force": "true",
            "interrupt": "%i" % self._default_interrupt,
        }

        data = kwargs.get(ATTR_DATA)
        if data:
            if ATTR_DURATION in data:
                duration = data.get(ATTR_DURATION)
                try:
                    payload[ATTR_DURATION] = "%i" % int(duration)
                except ValueError:
                    _LOGGER.warning("Invalid duration-value: %s", str(duration))
            if ATTR_FONTSIZE in data:
                fontsize = data.get(ATTR_FONTSIZE)
                if fontsize in FONTSIZES:
                    payload[ATTR_FONTSIZE] = "%i" % FONTSIZES.get(fontsize)
                else:
                    _LOGGER.warning("Invalid fontsize-value: %s", str(fontsize))
            if ATTR_POSITION in data:
                position = data.get(ATTR_POSITION)
                if position in POSITIONS:
                    payload[ATTR_POSITION] = "%i" % POSITIONS.get(position)
                else:
                    _LOGGER.warning("Invalid position-value: %s", str(position))
            if ATTR_TRANSPARENCY in data:
                transparency = data.get(ATTR_TRANSPARENCY)
                if transparency in TRANSPARENCIES:
                    payload[ATTR_TRANSPARENCY] = "%i" % TRANSPARENCIES.get(transparency)
                else:
                    _LOGGER.warning("Invalid transparency-value: %s", str(transparency))
            if ATTR_COLOR in data:
                color = data.get(ATTR_COLOR)
                if color in COLORS:
                    payload[ATTR_BKGCOLOR] = "%s" % COLORS.get(color)
                else:
                    _LOGGER.warning("Invalid color-value: %s", str(color))
            if ATTR_INTERRUPT in data:
                interrupt = data.get(ATTR_INTERRUPT)
                try:
                    payload[ATTR_INTERRUPT] = "%i" % cv.boolean(interrupt)
                except vol.Invalid:
                    _LOGGER.warning("Invalid interrupt-value: %s", str(interrupt))
            filedata = data.get(ATTR_FILE) if data else None
            if filedata is not None:
                # Load from file or URL
                file_as_bytes = self.load_file(
                    url=filedata.get(ATTR_FILE_URL),
                    local_path=filedata.get(ATTR_FILE_PATH),
                    username=filedata.get(ATTR_FILE_USERNAME),
                    password=filedata.get(ATTR_FILE_PASSWORD),
                    auth=filedata.get(ATTR_FILE_AUTH),
                )
                if file_as_bytes:
                    payload[ATTR_IMAGE] = (
                        "image",
                        file_as_bytes,
                        "application/octet-stream",
                        {"Expires": "0"},
                    )

        try:
            _LOGGER.debug("Payload: %s", str(payload))
            response = requests.post(self._target, files=payload, timeout=self._timeout)
            if response.status_code != HTTP_OK:
                _LOGGER.error("Error sending message: %s", str(response))
        except requests.exceptions.ConnectionError as err:
            _LOGGER.error("Error communicating with %s: %s", self._target, str(err))

    def load_file(
        self, url=None, local_path=None, username=None, password=None, auth=None
    ):
        """Load image/document/etc from a local path or URL."""
        try:
            if url is not None:
                # Check whether authentication parameters are provided
                if username is not None and password is not None:
                    # Use digest or basic authentication
                    if ATTR_FILE_AUTH_DIGEST == auth:
                        auth_ = HTTPDigestAuth(username, password)
                    else:
                        auth_ = HTTPBasicAuth(username, password)
                    # Load file from URL with authentication
                    req = requests.get(url, auth=auth_, timeout=DEFAULT_TIMEOUT)
                else:
                    # Load file from URL without authentication
                    req = requests.get(url, timeout=DEFAULT_TIMEOUT)
                return req.content

            if local_path is not None:
                # Check whether path is whitelisted in configuration.yaml
                if self.is_allowed_path(local_path):
                    return open(local_path, "rb")  # pylint: disable=consider-using-with
                _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            else:
                _LOGGER.warning("Neither URL nor local path found in params!")

        except OSError as error:
            _LOGGER.error("Can't load from url or local path: %s", error)

        return None
