"""Notifications for Android TV notification service."""

from __future__ import annotations

from io import BufferedReader
import logging
from typing import Any

from notifications_android_tv import Notifications
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_COLOR,
    ATTR_DURATION,
    ATTR_FONTSIZE,
    ATTR_ICON,
    ATTR_ICON_AUTH,
    ATTR_ICON_AUTH_DIGEST,
    ATTR_ICON_PASSWORD,
    ATTR_ICON_PATH,
    ATTR_ICON_URL,
    ATTR_ICON_USERNAME,
    ATTR_IMAGE,
    ATTR_IMAGE_AUTH,
    ATTR_IMAGE_AUTH_DIGEST,
    ATTR_IMAGE_PASSWORD,
    ATTR_IMAGE_PATH,
    ATTR_IMAGE_URL,
    ATTR_IMAGE_USERNAME,
    ATTR_INTERRUPT,
    ATTR_POSITION,
    ATTR_TRANSPARENCY,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> NFAndroidTVNotificationService | None:
    """Get the NFAndroidTV notification service."""
    if discovery_info is None:
        return None
    notify = await hass.async_add_executor_job(Notifications, discovery_info[CONF_HOST])
    return NFAndroidTVNotificationService(
        notify,
        hass.config.is_allowed_path,
    )


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(
        self,
        notify: Notifications,
        is_allowed_path: Any,
    ) -> None:
        """Initialize the service."""
        self.notify = notify
        self.is_allowed_path = is_allowed_path

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a Android TV device."""
        data: dict | None = kwargs.get(ATTR_DATA)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        duration = None
        fontsize = None
        position = None
        transparency = None
        bkgcolor = None
        interrupt = False
        icon = None
        image_file = None
        if data:
            if ATTR_DURATION in data:
                try:
                    duration = int(
                        data.get(ATTR_DURATION, Notifications.DEFAULT_DURATION)
                    )
                except ValueError:
                    _LOGGER.warning(
                        "Invalid duration-value: %s", data.get(ATTR_DURATION)
                    )
            if ATTR_FONTSIZE in data:
                if data.get(ATTR_FONTSIZE) in Notifications.FONTSIZES:
                    fontsize = data.get(ATTR_FONTSIZE)
                else:
                    _LOGGER.warning(
                        "Invalid fontsize-value: %s", data.get(ATTR_FONTSIZE)
                    )
            if ATTR_POSITION in data:
                if data.get(ATTR_POSITION) in Notifications.POSITIONS:
                    position = data.get(ATTR_POSITION)
                else:
                    _LOGGER.warning(
                        "Invalid position-value: %s", data.get(ATTR_POSITION)
                    )
            if ATTR_TRANSPARENCY in data:
                if data.get(ATTR_TRANSPARENCY) in Notifications.TRANSPARENCIES:
                    transparency = data.get(ATTR_TRANSPARENCY)
                else:
                    _LOGGER.warning(
                        "Invalid transparency-value: %s",
                        data.get(ATTR_TRANSPARENCY),
                    )
            if ATTR_COLOR in data:
                if data.get(ATTR_COLOR) in Notifications.BKG_COLORS:
                    bkgcolor = data.get(ATTR_COLOR)
                else:
                    _LOGGER.warning("Invalid color-value: %s", data.get(ATTR_COLOR))
            if ATTR_INTERRUPT in data:
                try:
                    interrupt = cv.boolean(data.get(ATTR_INTERRUPT))
                except vol.Invalid:
                    _LOGGER.warning(
                        "Invalid interrupt-value: %s", data.get(ATTR_INTERRUPT)
                    )
            if imagedata := data.get(ATTR_IMAGE):
                if isinstance(imagedata, str):
                    image_file = (
                        self.load_file(url=imagedata)
                        if imagedata.startswith("http")
                        else self.load_file(local_path=imagedata)
                    )
                elif isinstance(imagedata, dict):
                    image_file = self.load_file(
                        url=imagedata.get(ATTR_IMAGE_URL),
                        local_path=imagedata.get(ATTR_IMAGE_PATH),
                        username=imagedata.get(ATTR_IMAGE_USERNAME),
                        password=imagedata.get(ATTR_IMAGE_PASSWORD),
                        auth=imagedata.get(ATTR_IMAGE_AUTH),
                    )
                else:
                    raise ServiceValidationError(
                        "Invalid image provided",
                        translation_domain=DOMAIN,
                        translation_key="invalid_notification_image",
                        translation_placeholders={"type": type(imagedata).__name__},
                    )
            if icondata := data.get(ATTR_ICON):
                if isinstance(icondata, str):
                    icondata = (
                        self.load_file(url=icondata)
                        if icondata.startswith("http")
                        else self.load_file(local_path=icondata)
                    )
                elif isinstance(icondata, dict):
                    icon = self.load_file(
                        url=icondata.get(ATTR_ICON_URL),
                        local_path=icondata.get(ATTR_ICON_PATH),
                        username=icondata.get(ATTR_ICON_USERNAME),
                        password=icondata.get(ATTR_ICON_PASSWORD),
                        auth=icondata.get(ATTR_ICON_AUTH),
                    )
                else:
                    raise ServiceValidationError(
                        "Invalid Icon provided",
                        translation_domain=DOMAIN,
                        translation_key="invalid_notification_icon",
                        translation_placeholders={"type": type(icondata).__name__},
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
        self,
        url: str | None = None,
        local_path: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth: str | None = None,
    ) -> BufferedReader | bytes | None:
        """Load image/document/etc from a local path or URL."""
        try:
            if url is not None:
                # Check whether authentication parameters are provided
                if username is not None and password is not None:
                    # Use digest or basic authentication
                    auth_: HTTPDigestAuth | HTTPBasicAuth
                    if auth in (ATTR_IMAGE_AUTH_DIGEST, ATTR_ICON_AUTH_DIGEST):
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
                    return open(local_path, "rb")
                _LOGGER.warning("'%s' is not secure to load data from!", local_path)
            else:
                _LOGGER.warning("Neither URL nor local path found in params!")

        except OSError as error:
            _LOGGER.error("Can't load from url or local path: %s", error)

        return None
