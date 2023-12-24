"""TvOverlay notification service for Android TV."""
from __future__ import annotations

import logging
import os.path
from typing import Any
import uuid

from tvoverlay import ImageUrlSource, Notifications
from tvoverlay.const import (
    COLOR_GREEN,
    DEFAULT_APP_NAME,
    DEFAULT_SMALL_ICON,
    DEFAULT_SOURCE_NAME,
    Positions,
    Shapes,
)
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_DURATION = "5"

# Parameters for Notifications
ATTR_ID = "id"
ATTR_APP_TITLE = "app_title"
ATTR_SOURCE_NAME = "source_name"
ATTR_APP_ICON = "app_icon"
ATTR_BADGE_ICON = "badge_icon"
ATTR_BADGE_COLOR = "badge_color"
ATTR_POSITION = "position"
ATTR_DURATION = "duration"
ATTR_IMAGE = "image"
ATTR_VIDEO = "video"

# Attributes for image and app icon
ATTR_IMAGE_URL = "url"
ATTR_IMAGE_PATH = "path"
ATTR_IMAGE_ICON = "mdi_icon"
ATTR_IMAGE_USERNAME = "username"
ATTR_IMAGE_PASSWORD = "password"
ATTR_IMAGE_AUTH = "auth"

# Additional Parameters for Persistent Notifications
ATTR_PERSISTENT = "is_persistent"
ATTR_MESSAGE_COLOR = "message_color"
ATTR_BORDER_COLOR = "border_color"
ATTR_BG_COLOR = "bg_color"
ATTR_SHAPE = "shape"
ATTR_VISIBLE = "visible"

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TvOverlayNotificationService | None:
    """Get the TvOverlay notification service."""
    return TvOverlayNotificationService(discovery_info) if discovery_info else None


class TvOverlayNotificationService(BaseNotificationService):
    """Notification service for TvOverlay."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the service."""
        self.notify = Notifications(config[CONF_HOST])

    async def _is_valid_url(self, url: str) -> bool:
        """Check if a valid url and in allowlist_external_urls."""
        try:
            cv.url(url)
        except vol.Invalid:
            _LOGGER.warning("Invalid URL: %s", url)
            return False

        if self.hass.config.is_allowed_external_url(url):
            return True

        _LOGGER.warning(
            "URL is not allowed: %s, check allowlist_external_urls in configuration.yaml",
            url,
        )
        return False

    async def _is_valid_file(self, filename: str) -> bool:
        """Check if a file exists on disk and is in allowlist_external_dirs."""
        if not self.hass.config.is_allowed_path(filename) or not os.path.isfile(
            filename
        ):
            _LOGGER.warning(
                "Validation failed for file: %s. Check allowlist_external_dirs in configuration.yaml",
                filename,
            )
            return False
        return True

    async def _validate_image(self, image_data: str) -> str | None:
        """Validate image_data is valid and in allowed list."""
        if await self._is_valid_url(image_data):
            return image_data
        if image_data.startswith("mdi:"):
            return image_data
        if await self._is_valid_file(image_data):
            return image_data
        return None

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a TvOverlay device."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        _LOGGER.debug("Notification additional data attributes: %s", data)
        message_id = data.get(ATTR_ID, str(uuid.uuid1()))
        app_title = data.get(ATTR_APP_TITLE) or DEFAULT_APP_NAME
        source_name = data.get(ATTR_SOURCE_NAME) or DEFAULT_SOURCE_NAME
        app_icon: str | ImageUrlSource | None = None
        app_icon_data = data.get(ATTR_APP_ICON)
        if isinstance(app_icon_data, str):
            app_icon = await self._validate_image(app_icon_data)
        else:
            app_icon = (
                await self._populate_image(app_icon_data) if app_icon_data else None
            )

        badge_icon = data.get(ATTR_BADGE_ICON) or DEFAULT_SMALL_ICON
        badge_color = data.get(ATTR_BADGE_COLOR) or COLOR_GREEN
        position = (
            data.get(ATTR_POSITION, Positions.TOP_RIGHT.value)
            or Positions.TOP_RIGHT.value
        )

        if position not in [member.value for member in Positions]:
            position = Positions.TOP_RIGHT.value
            _LOGGER.warning(
                "Invalid position value: %s. Has to be one of: %s",
                position,
                [member.value for member in Positions],
            )

        duration: str = (str(data.get(ATTR_DURATION))) or DEFAULT_DURATION

        image: str | ImageUrlSource | None = None
        image_data = data.get(ATTR_IMAGE)
        if isinstance(image_data, str):
            image = await self._validate_image(image_data)
        else:
            image = await self._populate_image(image_data) if image_data else None

        video: str | None = data.get(ATTR_VIDEO)

        is_persistent = cv.boolean(data.get(ATTR_PERSISTENT, False))
        message_color = data.get(ATTR_MESSAGE_COLOR)
        border_color = data.get(ATTR_BORDER_COLOR)
        bg_color = data.get(ATTR_BG_COLOR)
        shape = data.get(ATTR_SHAPE, Shapes.CIRCLE.value) or Shapes.CIRCLE.value

        if shape not in [member.value for member in Shapes]:
            shape = Shapes.CIRCLE.value
            _LOGGER.warning(
                "Invalid shape value: %s. Has to be one of: %s",
                shape,
                [member.value for member in Shapes],
            )

        visible = cv.boolean(data.get(ATTR_VISIBLE, True))

        if is_persistent:
            _LOGGER.info("Sending TvOverlay persistent notification")
            await self.notify.async_send_fixed(
                message,
                id=message_id,
                icon=badge_icon,
                iconColor=badge_color,
                textColor=message_color,
                borderColor=border_color,
                backgroundColor=bg_color,
                shape=shape,
                duration=duration,
                visible=visible,
            )
        else:
            _LOGGER.info("Sending TvOverlay notification")
            await self.notify.async_send(
                message,
                id=message_id,
                title=title,
                deviceSourceName=source_name,
                appTitle=app_title,
                appIcon=app_icon,
                smallIcon=badge_icon,
                smallIconColor=badge_color,
                image=image,
                video=video,
                corner=position,
                duration=duration,
            )

    async def _populate_image(
        self, data: dict[str, Any]
    ) -> ImageUrlSource | str | None:
        """Populate image from a local path or URL."""
        if data:
            url = data.get(ATTR_IMAGE_URL)
            local_path = data.get(ATTR_IMAGE_PATH)
            mdi_icon = data.get(ATTR_IMAGE_ICON)
            username = data.get(ATTR_IMAGE_USERNAME)
            password = data.get(ATTR_IMAGE_PASSWORD)
            auth = data.get(ATTR_IMAGE_AUTH)

            if url and await self._is_valid_url(url):
                _LOGGER.debug("Using image URL: %s", url)
                return ImageUrlSource(
                    url, username=username, password=password, auth=auth
                )

            if local_path and await self._is_valid_file(local_path):
                _LOGGER.debug("Using local image path: %s", local_path)
                return local_path

            if mdi_icon and mdi_icon.startswith("mdi:"):
                _LOGGER.debug("Using MDI icon: %s", mdi_icon)
                return mdi_icon

        _LOGGER.warning(
            "No valid URL, local_path or mdi_icon found in image attributes"
        )
        return None
