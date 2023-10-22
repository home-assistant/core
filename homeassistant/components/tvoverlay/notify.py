"""TvOverlay notification service for Android TV."""
from __future__ import annotations

import logging
from typing import Any
import uuid

from tvoverlay import ImageUrlSource, Notifications
from tvoverlay.const import (
    COLOR_GREEN,
    DEFAULT_APP_NAME,
    DEFAULT_DURATION,
    DEFAULT_SMALL_ICON,
    DEFAULT_SOURCE_NAME,
    Positions,
    Shapes,
)

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

from .const import (
    ATTR_APP_ICON,
    ATTR_APP_TITLE,
    ATTR_BADGE_COLOR,
    ATTR_BADGE_ICON,
    ATTR_BG_COLOR,
    ATTR_BORDER_COLOR,
    ATTR_DURATION,
    ATTR_ID,
    ATTR_IMAGE,
    ATTR_IMAGE_AUTH,
    ATTR_IMAGE_ICON,
    ATTR_IMAGE_PASSWORD,
    ATTR_IMAGE_PATH,
    ATTR_IMAGE_URL,
    ATTR_IMAGE_USERNAME,
    ATTR_PERSISTENT,
    ATTR_POSITION,
    ATTR_SHAPE,
    ATTR_SOURCE_NAME,
    ATTR_TEXT_COLOR,
    ATTR_VISIBLE,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TvOverlayNotificationService | None:
    """Get the TvOverlay notification service."""
    if discovery_info is None:
        return None
    notify = await hass.async_add_executor_job(Notifications, discovery_info[CONF_HOST])
    return TvOverlayNotificationService(
        notify,
        hass.config.is_allowed_path,
    )


class TvOverlayNotificationService(BaseNotificationService):
    """Notification service for TvOverlay."""

    def __init__(self, notify: Notifications, is_allowed_path: Any) -> None:
        """Initialize the service."""
        self.notify = notify
        self.is_allowed_path = is_allowed_path

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a TvOverlay device."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA, {}) or {}
        _LOGGER.debug("Notification additional data attributes: %s", data)
        message_id = data.get(ATTR_ID, str(uuid.uuid1()))
        app_title = data.get(ATTR_APP_TITLE, DEFAULT_APP_NAME) or DEFAULT_APP_NAME
        source_name = (
            data.get(ATTR_SOURCE_NAME, DEFAULT_SOURCE_NAME) or DEFAULT_SOURCE_NAME
        )
        app_icon: str | ImageUrlSource | None = None
        app_icon_data = data.get(ATTR_APP_ICON)
        if isinstance(app_icon_data, str):
            app_icon = app_icon_data
        else:
            app_icon = (
                await self.populate_image(app_icon_data) if app_icon_data else None
            )

        badge_icon = data.get(ATTR_BADGE_ICON, DEFAULT_SMALL_ICON) or DEFAULT_SMALL_ICON
        badge_color = data.get(ATTR_BADGE_COLOR, COLOR_GREEN) or COLOR_GREEN
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

        duration = data.get(ATTR_DURATION, DEFAULT_DURATION) or str(DEFAULT_DURATION)

        image: str | ImageUrlSource | None = None
        image_data = data.get(ATTR_IMAGE)
        if isinstance(image_data, str):
            image = image_data
        else:
            image = await self.populate_image(image_data) if image_data else None

        is_persistent = cv.boolean(data.get(ATTR_PERSISTENT, False))
        text_color = data.get(ATTR_TEXT_COLOR)
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
                textColor=text_color,
                borderColor=border_color,
                backgroundColor=bg_color,
                shape=shape,
                expiration=duration,
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
                corner=position,
                seconds=int(duration),
            )

    async def populate_image(self, data: dict[str, Any]) -> ImageUrlSource | str | None:
        """Populate image from a local path or URL."""
        if data:
            url = data.get(ATTR_IMAGE_URL)
            local_path = data.get(ATTR_IMAGE_PATH)
            mdi_icon = data.get(ATTR_IMAGE_ICON)
            username = data.get(ATTR_IMAGE_USERNAME)
            password = data.get(ATTR_IMAGE_PASSWORD)
            auth = data.get(ATTR_IMAGE_AUTH)

            if url and (url.startswith("http://") or url.startswith("https://")):
                _LOGGER.debug("Using image URL: %s", url)
                return ImageUrlSource(
                    url, username=username, password=password, auth=auth
                )

            if local_path and self.is_allowed_path(local_path):
                _LOGGER.debug("Using local image path: %s", local_path)
                return local_path

            if mdi_icon and mdi_icon.startswith("mdi:"):
                _LOGGER.debug("Using MDI icon: %s", mdi_icon)
                return mdi_icon

        _LOGGER.warning(
            "No valid URL, local_path, or mdi_icon found in image attributes"
        )
        return None
