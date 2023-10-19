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

    def __init__(
        self,
        notify: Notifications,
        is_allowed_path: Any,
    ) -> None:
        """Initialize the service."""
        self.notify = notify
        self.is_allowed_path = is_allowed_path

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a TvOverlay device."""
        data: dict[str, Any] | None = kwargs.get(ATTR_DATA)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        message_id: str | None = str(uuid.uuid1())
        app_title: str | None = DEFAULT_APP_NAME
        source_name: str | None = DEFAULT_SOURCE_NAME
        app_icon: str | ImageUrlSource | None = None
        badge_icon: str | None = DEFAULT_SMALL_ICON
        badge_color: str | None = COLOR_GREEN
        position: str = Positions.TOP_RIGHT.value
        duration: str = str(DEFAULT_DURATION)
        image: str | ImageUrlSource | None = None
        is_persistent: bool | None = False
        text_color: str | None = None
        border_color: str | None = None
        bg_color: str | None = None
        shape: str = Shapes.CIRCLE.value
        visible: bool | None = True

        if data:
            message_id = data.get(ATTR_ID, message_id)
            app_title = data.get(ATTR_APP_TITLE, app_title)
            source_name = data.get(ATTR_SOURCE_NAME, source_name)

            app_icon_data = data.get(ATTR_APP_ICON)
            if app_icon_data:
                app_icon = self.populate_image(**app_icon_data)

            badge_icon = data.get(ATTR_BADGE_ICON, badge_icon)
            badge_color = data.get(ATTR_BADGE_COLOR, badge_color)
            position = data.get(ATTR_POSITION, Positions.TOP_RIGHT.value)
            if position not in [member.value for member in Positions]:
                _LOGGER.warning(
                    "Invalid position value: %s. Has to be one of: %s",
                    position,
                    [member.value for member in Positions],
                )

            duration = str(data.get(ATTR_DURATION, duration))

            image_data = data.get(ATTR_IMAGE)
            if image_data:
                image = self.populate_image(**image_data)

            is_persistent = cv.boolean(data.get(ATTR_PERSISTENT, is_persistent))
            text_color = data.get(ATTR_TEXT_COLOR, text_color)
            border_color = data.get(ATTR_BORDER_COLOR, border_color)
            bg_color = data.get(ATTR_BG_COLOR, bg_color)

            shape = data.get(ATTR_SHAPE, shape)
            if shape not in [member.value for member in Shapes]:
                _LOGGER.warning(
                    "Invalid shape value: %s. Has to be one of: %s",
                    shape,
                    [member.value for member in Shapes],
                )

            visible = cv.boolean(data.get(ATTR_VISIBLE, visible))

        if is_persistent:
            await self.notify.async_send_fixed(
                message,
                id=message_id,
                icon=badge_icon,
                iconColor=app_title,
                textColor=text_color,
                borderColor=border_color,
                backgroundColor=bg_color,
                shape=shape,
                expiration=duration,
                visible=visible,
            )
        else:
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

    def populate_image(
        self,
        url: str | None = None,
        local_path: str | None = None,
        mdi_icon: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth: str | None = None,
    ) -> ImageUrlSource | str | None:
        """Populate image from a local path or URL."""
        if url is not None:
            if url.startswith("http://") or url.startswith("https://"):
                return ImageUrlSource(
                    url, username=username, password=password, auth=auth
                )
            _LOGGER.warning("'%s' is not  valid http or https url!", local_path)

        if local_path is not None:
            # Check whether path is whitelisted in configuration.yaml
            if self.is_allowed_path(local_path):
                return local_path
            _LOGGER.warning(
                "'%s' is not secure to load data. Check 'allowlist_external_dirs' configuration",
                local_path,
            )

        if mdi_icon is not None:
            if mdi_icon.startswith("mdi:"):
                return mdi_icon
            _LOGGER.warning(
                "'%s' is not a valid mdi icon. mdi:icon-name Expected!", mdi_icon
            )

        _LOGGER.warning(
            "Neither valid URL, local_path or mdi_icon found in image attributes!"
        )

        return None
