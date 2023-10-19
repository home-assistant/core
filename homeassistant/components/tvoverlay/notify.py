"""TvOverlay notification service for Android TV."""
from __future__ import annotations

import logging
from typing import Any
import uuid

from tvoverlay import ImageUrlSource, Notifications
from tvoverlay.const import (
    COLOR_GREEN,
    DEFAULT_APP_ICON,
    DEFAULT_APP_NAME,
    DEFAULT_DURATION,
    DEFAULT_SMALL_ICON,
    DEFAULT_SOURCE_NAME,
    Positions,
)

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_APP_ICON,
    ATTR_APP_TITLE,
    ATTR_BADGE_COLOR,
    ATTR_BADGE_ICON,
    ATTR_DURATION,
    ATTR_ID,
    ATTR_IMAGE,
    ATTR_IMAGE_AUTH,
    ATTR_IMAGE_ICON,
    ATTR_IMAGE_PASSWORD,
    ATTR_IMAGE_PATH,
    ATTR_IMAGE_URL,
    ATTR_IMAGE_USERNAME,
    ATTR_POSITION,
    ATTR_SOURCE_NAME,
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

        if data:
            if ATTR_ID in data:
                try:
                    message_id = data.get(ATTR_ID)
                except ValueError:
                    _LOGGER.warning("Invalid id value: %s", data.get(ATTR_ID))
            if ATTR_APP_TITLE in data:
                try:
                    app_title = data.get(ATTR_APP_TITLE)
                except ValueError:
                    _LOGGER.warning(
                        "Invalid app_title value: %s", data.get(ATTR_APP_TITLE)
                    )
            if ATTR_SOURCE_NAME in data:
                try:
                    source_name = data.get(ATTR_SOURCE_NAME)
                except ValueError:
                    _LOGGER.warning(
                        "Invalid source_name value: %s", data.get(ATTR_SOURCE_NAME)
                    )
            if app_icon_data := data.get(ATTR_APP_ICON):
                try:
                    if isinstance(app_icon_data, str):
                        app_icon = app_icon_data
                    else:
                        app_icon = self.populate_image(
                            url=app_icon_data.get(ATTR_IMAGE_URL),
                            local_path=app_icon_data.get(ATTR_IMAGE_PATH),
                            mdi_icon=app_icon_data.get(ATTR_IMAGE_ICON),
                            username=app_icon_data.get(ATTR_IMAGE_USERNAME),
                            password=app_icon_data.get(ATTR_IMAGE_PASSWORD),
                            auth=app_icon_data.get(ATTR_IMAGE_AUTH),
                        )
                except ValueError:
                    _LOGGER.warning(
                        "Invalid image attributes: %s", data.get(ATTR_IMAGE)
                    )
            else:
                app_icon = DEFAULT_APP_ICON
            if ATTR_BADGE_ICON in data:
                try:
                    badge_icon = data.get(ATTR_BADGE_ICON)
                except ValueError:
                    _LOGGER.warning(
                        "Invalid badge_icon value: %s", data.get(ATTR_BADGE_ICON)
                    )
            if ATTR_BADGE_COLOR in data:
                try:
                    badge_color = data.get(ATTR_BADGE_COLOR)
                except ValueError:
                    _LOGGER.warning(
                        "Invalid badge_color value: %s",
                        data.get(ATTR_BADGE_COLOR),
                    )
            if ATTR_POSITION in data:
                if data.get(ATTR_POSITION) in [member.value for member in Positions]:
                    position = data.get(ATTR_POSITION, Positions.TOP_RIGHT.value)
                else:
                    _LOGGER.warning(
                        "Invalid position value: %s. Has to be one of: %s",
                        data.get(ATTR_POSITION),
                        [member.value for member in Positions],
                    )
            if ATTR_DURATION in data:
                try:
                    duration = str(data.get(ATTR_DURATION))
                except ValueError:
                    _LOGGER.warning(
                        "Invalid duration value: %s", data.get(ATTR_DURATION)
                    )
            if image_data := data.get(ATTR_IMAGE):
                try:
                    if isinstance(image_data, str):
                        image = image_data
                    else:
                        image = self.populate_image(
                            url=image_data.get(ATTR_IMAGE_URL),
                            local_path=image_data.get(ATTR_IMAGE_PATH),
                            mdi_icon=image_data.get(ATTR_IMAGE_ICON),
                            username=image_data.get(ATTR_IMAGE_USERNAME),
                            password=image_data.get(ATTR_IMAGE_PASSWORD),
                            auth=image_data.get(ATTR_IMAGE_AUTH),
                        )
                except ValueError:
                    _LOGGER.warning(
                        "Invalid image attributes: %s", data.get(ATTR_IMAGE)
                    )

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
