"""TvOverlay notification service for Android TV."""
from __future__ import annotations

import logging
import os.path
from pathlib import Path
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
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

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
        except vol.Invalid as err:
            raise ServiceValidationError(
                f"Invalid url '{url}'",
                translation_domain=DOMAIN,
                translation_key="invalid_url",
                translation_placeholders={
                    "url": url,
                },
            ) from err

        if self.hass.config.is_allowed_external_url(url):
            return True

        allow_url_list = "allowlist_external_urls"
        help_url = "https://www.home-assistant.io/docs/configuration/basic/"

        raise ServiceValidationError(
            f"Cannot send TvOverlay notification with image url '{url}' which is not secure to load data from."
            f"Only url's added to `{allow_url_list}` are accessible. "
            f"See {help_url} for more information.",
            translation_domain=DOMAIN,
            translation_key="remote_url_not_allowed",
            translation_placeholders={
                "url": url,
                "allow_url_list": allow_url_list,
                "help_url": help_url,
            },
        )

    async def _is_valid_file(self, filename: str) -> bool:
        """Check if a file exists on disk and is in allowlist_external_dirs."""

        file_path = Path(filename).parent
        if (
            os.path.exists(file_path)
            and os.path.isfile(filename)
            and self.hass.config.is_allowed_path(str(file_path))
        ):
            return True

        allow_file_list = "allowlist_external_dirs"
        file_name = os.path.basename(filename)
        help_url = "https://www.home-assistant.io/docs/configuration/basic/"
        raise ServiceValidationError(
            f"Cannot send TvOverlay notification with image file '{file_name}' "
            f"from directory '{str(file_path)}' which is not secure to load data from. "
            f"Only folders added to `{allow_file_list}` are accessible. "
            f"See {help_url} for more information.",
            translation_domain=DOMAIN,
            translation_key="remote_file_not_allowed",
            translation_placeholders={
                "allow_file_list": allow_file_list,
                "file_path": str(file_path),
                "file_name": file_name,
                "help_url": help_url,
            },
        )

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
        app_title = data.get(ATTR_APP_TITLE, DEFAULT_APP_NAME)
        source_name = data.get(ATTR_SOURCE_NAME, DEFAULT_SOURCE_NAME)
        app_icon: str | ImageUrlSource | None = None
        app_icon_data = data.get(ATTR_APP_ICON)
        if isinstance(app_icon_data, str):
            app_icon = await self._validate_image(app_icon_data)
        else:
            app_icon = (
                await self._populate_image(app_icon_data) if app_icon_data else None
            )

        badge_icon = data.get(ATTR_BADGE_ICON, DEFAULT_SMALL_ICON)
        badge_color = data.get(ATTR_BADGE_COLOR, COLOR_GREEN)
        position = data.get(ATTR_POSITION, Positions.TOP_RIGHT.value)
        positions_values = [member.value for member in Positions]

        if position not in positions_values:
            raise ServiceValidationError(
                f"Invalid position value '{position}', "
                f"Has to be one of {str(positions_values)}.",
                translation_domain=DOMAIN,
                translation_key="invalid_positon_value",
                translation_placeholders={
                    "position": position,
                    "positions_values": str(positions_values),
                },
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
        shape = data.get(ATTR_SHAPE, Shapes.CIRCLE.value)
        shape_values = [member.value for member in Shapes]

        if shape not in shape_values:
            raise ServiceValidationError(
                f"Invalid shape value '{shape}', "
                f"Has to be one of {str(shape_values)}.",
                translation_domain=DOMAIN,
                translation_key="invalid_shape_value",
                translation_placeholders={
                    "shape": shape,
                    "shape_values": str(shape_values),
                },
            )

        visible = cv.boolean(data.get(ATTR_VISIBLE, True))

        if is_persistent:
            _LOGGER.debug("Sending TvOverlay persistent notification")
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
            _LOGGER.debug("Sending TvOverlay notification")
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

        raise ServiceValidationError(
            "Invalid notification image. No valid URL, local_path or mdi_icon found in image attributes.",
            translation_domain=DOMAIN,
            translation_key="invalid_image",
        )
