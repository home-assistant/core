"""Notifications for Android TV notification service."""
import logging

from notifications_android_tv import Notifications
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
from homeassistant.const import ATTR_ICON, CONF_HOST, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
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
    ATTR_INTERRUPT,
    ATTR_POSITION,
    ATTR_TRANSPARENCY,
    CONF_COLOR,
    CONF_DURATION,
    CONF_FONTSIZE,
    CONF_INTERRUPT,
    CONF_POSITION,
    CONF_TRANSPARENCY,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# Deprecated in Home Assistant 2021.8
PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_DURATION): vol.Coerce(int),
                vol.Optional(CONF_FONTSIZE): vol.In(Notifications.FONTSIZES.keys()),
                vol.Optional(CONF_POSITION): vol.In(Notifications.POSITIONS.keys()),
                vol.Optional(CONF_TRANSPARENCY): vol.In(
                    Notifications.TRANSPARENCIES.keys()
                ),
                vol.Optional(CONF_COLOR): vol.In(Notifications.BKG_COLORS.keys()),
                vol.Optional(CONF_TIMEOUT): vol.Coerce(int),
                vol.Optional(CONF_INTERRUPT): cv.boolean,
            }
        ),
    )
)


async def async_get_service(hass: HomeAssistant, config, discovery_info=None):
    """Get the NFAndroidTV notification service."""
    if discovery_info is not None:
        notify = await hass.async_add_executor_job(
            Notifications, discovery_info[CONF_HOST]
        )
        return NFAndroidTVNotificationService(
            notify,
            hass.config.is_allowed_path,
        )
    notify = await hass.async_add_executor_job(Notifications, config.get(CONF_HOST))
    return NFAndroidTVNotificationService(
        notify,
        hass.config.is_allowed_path,
    )


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(
        self,
        notify: Notifications,
        is_allowed_path,
    ):
        """Initialize the service."""
        self.notify = notify
        self.is_allowed_path = is_allowed_path

    def send_message(self, message="", **kwargs):
        """Send a message to a Android TV device."""
        data = kwargs.get(ATTR_DATA)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        duration = None
        fontsize = None
        position = None
        transparency = None
        bkgcolor = None
        interrupt = None
        icon = None
        image_file = None
        if data:
            if ATTR_DURATION in data:
                try:
                    duration = int(data.get(ATTR_DURATION))
                except ValueError:
                    _LOGGER.warning(
                        "Invalid duration-value: %s", str(data.get(ATTR_DURATION))
                    )
            if ATTR_FONTSIZE in data:
                if data.get(ATTR_FONTSIZE) in Notifications.FONTSIZES:
                    fontsize = data.get(ATTR_FONTSIZE)
                else:
                    _LOGGER.warning(
                        "Invalid fontsize-value: %s", str(data.get(ATTR_FONTSIZE))
                    )
            if ATTR_POSITION in data:
                if data.get(ATTR_POSITION) in Notifications.POSITIONS:
                    position = data.get(ATTR_POSITION)
                else:
                    _LOGGER.warning(
                        "Invalid position-value: %s", str(data.get(ATTR_POSITION))
                    )
            if ATTR_TRANSPARENCY in data:
                if data.get(ATTR_TRANSPARENCY) in Notifications.TRANSPARENCIES:
                    transparency = data.get(ATTR_TRANSPARENCY)
                else:
                    _LOGGER.warning(
                        "Invalid transparency-value: %s",
                        str(data.get(ATTR_TRANSPARENCY)),
                    )
            if ATTR_COLOR in data:
                if data.get(ATTR_COLOR) in Notifications.BKG_COLORS:
                    bkgcolor = data.get(ATTR_COLOR)
                else:
                    _LOGGER.warning(
                        "Invalid color-value: %s", str(data.get(ATTR_COLOR))
                    )
            if ATTR_INTERRUPT in data:
                try:
                    interrupt = cv.boolean(data.get(ATTR_INTERRUPT))
                except vol.Invalid:
                    _LOGGER.warning(
                        "Invalid interrupt-value: %s", str(data.get(ATTR_INTERRUPT))
                    )
            filedata = data.get(ATTR_FILE) if data else None
            if filedata is not None:
                if ATTR_ICON in filedata:
                    icon = self.load_file(
                        url=filedata.get(ATTR_ICON),
                        local_path=filedata.get(ATTR_FILE_PATH),
                        username=filedata.get(ATTR_FILE_USERNAME),
                        password=filedata.get(ATTR_FILE_PASSWORD),
                        auth=filedata.get(ATTR_FILE_AUTH),
                    )
                image_file = self.load_file(
                    url=filedata.get(ATTR_FILE_URL),
                    local_path=filedata.get(ATTR_FILE_PATH),
                    username=filedata.get(ATTR_FILE_USERNAME),
                    password=filedata.get(ATTR_FILE_PASSWORD),
                    auth=filedata.get(ATTR_FILE_AUTH),
                )
        self.notify.send(
            message,
            title=title,
            duration=duration,
            fontsize=fontsize,
            position=position,
            bkgcolor=bkgcolor,
            transparency=transparency,
            interrupt=interrupt,
            icon=icon,
            image_file=image_file,
        )

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
