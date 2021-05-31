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
from homeassistant.const import CONF_HOST, CONF_TIMEOUT, HTTP_OK
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_BKGCOLOR,
    ATTR_COLOR,
    ATTR_DURATION,
    ATTR_FILE,
    ATTR_FILE_AUTH,
    ATTR_FILE_AUTH_DIGEST,
    ATTR_FILE_PASSWORD,
    ATTR_FILE_PATH,
    ATTR_FILE_URL,
    ATTR_FILE_USERNAME,
    ATTR_FONTSIZE,
    ATTR_IMAGE,
    ATTR_INTERRUPT,
    ATTR_POSITION,
    ATTR_TRANSPARENCY,
    COLORS,
    CONF_COLOR,
    CONF_DURATION,
    CONF_FONTSIZE,
    CONF_INTERRUPT,
    CONF_POSITION,
    CONF_TRANSPARENCY,
    DEFAULT_COLOR,
    DEFAULT_DURATION,
    DEFAULT_FONTSIZE,
    DEFAULT_ICON,
    DEFAULT_INTERRUPT,
    DEFAULT_POSITION,
    DEFAULT_TIMEOUT,
    DEFAULT_TRANSPARENCY,
    FONTSIZES,
    POSITIONS,
    TRANSPARENCIES,
)

_LOGGER = logging.getLogger(__name__)

# Deprecated in Home Assistant 2021.7
PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.Coerce(int),
                vol.Optional(CONF_FONTSIZE, default=DEFAULT_FONTSIZE): vol.In(
                    FONTSIZES.keys()
                ),
                vol.Optional(CONF_POSITION, default=DEFAULT_POSITION): vol.In(
                    POSITIONS.keys()
                ),
                vol.Optional(CONF_TRANSPARENCY, default=DEFAULT_TRANSPARENCY): vol.In(
                    TRANSPARENCIES.keys()
                ),
                vol.Optional(CONF_COLOR, default=DEFAULT_COLOR): vol.In(COLORS.keys()),
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
                vol.Optional(CONF_INTERRUPT, default=DEFAULT_INTERRUPT): cv.boolean,
            }
        ),
    )
)


async def async_get_service(hass, config, discovery_info=None):
    """Get the NFAndroidTV notification service."""
    if discovery_info is not None:
        return NFAndroidTVNotificationService(
            discovery_info[CONF_HOST],
            hass.config.is_allowed_path,
        )
    return NFAndroidTVNotificationService(
        config.get(CONF_HOST),
        hass.config.is_allowed_path,
    )


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(
        self,
        host,
        is_allowed_path,
    ):
        """Initialize the service."""
        self._target = f"http://{host}:7676"
        self.is_allowed_path = is_allowed_path

    def send_message(self, message="", **kwargs):
        """Send a message to a Android TV device."""
        _LOGGER.debug("Sending notification to: %s", self._target)

        payload = {
            "filename": (
                "icon.png",
                io.BytesIO(base64.b64decode(DEFAULT_ICON)),
                "application/octet-stream",
                {"Expires": "0"},
            ),
            "type": "0",
            "title": kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            "msg": message,
            "duration": "%i" % DEFAULT_DURATION,
            "fontsize": "%i" % FONTSIZES.get(DEFAULT_FONTSIZE),
            "position": "%i" % POSITIONS.get(DEFAULT_POSITION),
            "bkgcolor": "%s" % COLORS.get(DEFAULT_COLOR),
            "transparency": "%i" % TRANSPARENCIES.get(DEFAULT_TRANSPARENCY),
            "offset": "0",
            "app": ATTR_TITLE_DEFAULT,
            "force": "true",
            "interrupt": "%i" % DEFAULT_INTERRUPT,
        }

        data = kwargs.get(ATTR_DATA)
        if data:
            if ATTR_DURATION in data:
                try:
                    payload[ATTR_DURATION] = "%i" % int(data.get(ATTR_DURATION))
                except ValueError:
                    _LOGGER.warning(
                        "Invalid duration-value: %s", str(data.get(ATTR_DURATION))
                    )
            if ATTR_FONTSIZE in data:
                if data.get(ATTR_FONTSIZE) in FONTSIZES:
                    payload[ATTR_FONTSIZE] = "%i" % FONTSIZES.get(
                        data.get(ATTR_FONTSIZE)
                    )
                else:
                    _LOGGER.warning(
                        "Invalid fontsize-value: %s", str(data.get(ATTR_FONTSIZE))
                    )
            if ATTR_POSITION in data:
                if data.get(ATTR_POSITION) in POSITIONS:
                    payload[ATTR_POSITION] = "%i" % POSITIONS.get(
                        data.get(ATTR_POSITION)
                    )
                else:
                    _LOGGER.warning(
                        "Invalid position-value: %s", str(data.get(ATTR_POSITION))
                    )
            if ATTR_TRANSPARENCY in data:
                if data.get(ATTR_TRANSPARENCY) in TRANSPARENCIES:
                    payload[ATTR_TRANSPARENCY] = "%i" % TRANSPARENCIES.get(
                        data.get(ATTR_TRANSPARENCY)
                    )
                else:
                    _LOGGER.warning(
                        "Invalid transparency-value: %s",
                        str(data.get(ATTR_TRANSPARENCY)),
                    )
            if ATTR_COLOR in data:
                if data.get(ATTR_COLOR) in COLORS:
                    payload[ATTR_BKGCOLOR] = "%s" % COLORS.get(data.get(ATTR_COLOR))
                else:
                    _LOGGER.warning(
                        "Invalid color-value: %s", str(data.get(ATTR_COLOR))
                    )
            if ATTR_INTERRUPT in data:
                try:
                    payload[ATTR_INTERRUPT] = "%i" % cv.boolean(
                        data.get(ATTR_INTERRUPT)
                    )
                except vol.Invalid:
                    _LOGGER.warning(
                        "Invalid interrupt-value: %s", str(data.get(ATTR_INTERRUPT))
                    )
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
            response = requests.post(
                self._target, files=payload, timeout=DEFAULT_TIMEOUT
            )
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
                    with open(local_path, "rb") as path_handle:
                        return path_handle
                _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            else:
                _LOGGER.warning("Neither URL nor local path found in params!")

        except OSError as error:
            _LOGGER.error("Can't load from url or local path: %s", error)

        return None
