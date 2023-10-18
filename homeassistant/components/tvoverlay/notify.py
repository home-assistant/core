"""Notifications for Android TV notification service."""
from __future__ import annotations

from io import BufferedReader
import logging
from typing import Any

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from tvoverlay import Notifications

# import voluptuous as vol
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

# import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    # ATTR_IMAGE_PASSWORD,
    # ATTR_IMAGE_PATH,
    # ATTR_IMAGE_URL,
    # ATTR_IMAGE_USERNAME,
    # ATTR_ICON,
    # ATTR_ICON_AUTH,
    ATTR_ICON_AUTH_DIGEST,
    ATTR_ID,
    # ATTR_APP_TITLE,
    # ATTR_APP_ICON,
    # ATTR_COLOR,
    # ATTR_IMAGE,
    # ATTR_SMALL_ICON,
    # ATTR_LARGE_ICON,
    # ATTR_DURATION,
    # ATTR_POSITION,
    # ATTR_IMAGE_AUTH,
    ATTR_IMAGE_AUTH_DIGEST,
    DEFAULT_ID,
    # ATTR_ICON_PASSWORD,
    # ATTR_ICON_PATH,
    # ATTR_ICON_URL,
    # ATTR_ICON_USERNAME,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TVOverlayNotificationService | None:
    """Get the TVOverlay notification service."""
    if discovery_info is None:
        return None
    notify = await hass.async_add_executor_job(Notifications, discovery_info[CONF_HOST])
    return TVOverlayNotificationService(
        notify,
        hass.config.is_allowed_path,
    )


class TVOverlayNotificationService(BaseNotificationService):
    """Notification service for Notifications for TVOverlay."""

    def __init__(
        self,
        notify: Notifications,
        is_allowed_path: Any,
    ) -> None:
        """Initialize the service."""
        self.notify = notify
        self.is_allowed_path = is_allowed_path

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a TVOverlay device."""
        data: dict[str, Any] | None = kwargs.get(ATTR_DATA)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        msgid = None
        # appTitle = None
        # appIcon = None
        # color = None
        # smallIcon = None
        # largeIcon = None
        # position = None
        # duration = None
        # image_file = None
        # icon_file = None
        if data:
            if ATTR_ID in data:
                try:
                    msgid = data.get(ATTR_ID, DEFAULT_ID)
                except ValueError:
                    _LOGGER.warning("Invalid id-value: %s", data.get(ATTR_ID))
            # if ATTR_DURATION in data:
            #     try:
            #         duration = int(
            #             data.get(ATTR_DURATION, Notifications.DEFAULT_DURATION)
            #         )
            #     except ValueError:
            #         _LOGGER.warning(
            #             "Invalid duration-value: %s", data.get(ATTR_DURATION)
            #         )
            # if ATTR_POSITION in data:
            #     if data.get(ATTR_POSITION) in Notifications.POSITIONS:
            #         position = data.get(ATTR_POSITION)
            #     else:
            #         _LOGGER.warning(
            #             "Invalid position-value: %s", data.get(ATTR_POSITION)
            #         )
            # if ATTR_COLOR in data:
            #     if data.get(ATTR_COLOR) in Notifications.DEFAULT_COLOR:
            #         color = data.get(ATTR_COLOR)
            #     else:
            #         _LOGGER.warning("Invalid color-value: %s", data.get(ATTR_COLOR))
            # if imagedata := data.get(ATTR_IMAGE):
            #     image_file = self.load_file(
            #         url=imagedata.get(ATTR_IMAGE_URL),
            #         local_path=imagedata.get(ATTR_IMAGE_PATH),
            #         username=imagedata.get(ATTR_IMAGE_USERNAME),
            #         password=imagedata.get(ATTR_IMAGE_PASSWORD),
            #         auth=imagedata.get(ATTR_IMAGE_AUTH),
            #     )

            # if icondata := data.get(ATTR_ICON):
            #     icon_file = self.load_file(
            #         url=icondata.get(ATTR_ICON_URL),
            #         local_path=icondata.get(ATTR_ICON_PATH),
            #         username=icondata.get(ATTR_ICON_USERNAME),
            #         password=icondata.get(ATTR_ICON_PASSWORD),
            #         auth=icondata.get(ATTR_ICON_AUTH),
            #     )

        await self.notify.async_send(
            message,
            title=title,
            id=msgid,
            # appTitle=appTitle,
            # appIcon=icon_file,
            # color=color,
            # image=image_file,
            # smallIcon=smallIcon,
            # largeIcon=largeIcon,
            # corner=position,
            # seconds=duration,
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
