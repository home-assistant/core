"""Notifications for Android TV notification service."""

from __future__ import annotations

from typing import Any

from notifications_android_tv import (
    InvalidImageData,
    NotificationException,
    NotificationParams,
    Notifications,
)

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NFAndroidConfigEntry
from .const import DOMAIN


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> NFAndroidTVNotificationService | None:
    """Get the NFAndroidTV notification service."""
    if discovery_info is None:
        return None
    entry: NFAndroidConfigEntry | None = hass.config_entries.async_get_entry(
        discovery_info["entry_id"]
    )
    assert entry is not None
    notify = entry.runtime_data
    return NFAndroidTVNotificationService(notify)


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(self, notify: Notifications) -> None:
        """Initialize the service."""
        self.notify = notify

    def _check_path_is_allowed(self, notification_params: NotificationParams) -> None:
        """Check if any provided file path is allowed."""
        key: str | None = None
        if (
            notification_params.icon
            and (path := notification_params.icon.path)
            and not self.hass.config.is_allowed_path(path)
        ):
            key = "icon"
        elif (
            notification_params.image
            and (path := notification_params.image.path)
            and not self.hass.config.is_allowed_path(path)
        ):
            key = "image"
        if key and path:
            raise ServiceValidationError(
                "File path is not secure",
                translation_domain=DOMAIN,
                translation_key="unsecure_file_path",
                translation_placeholders={"key": key, "path": path},
            )

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a Android TV device."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        data: dict | None = kwargs.get(ATTR_DATA)
        notification_params: NotificationParams | None = None
        if data:
            try:
                notification_params = NotificationParams.from_dict(data)
            except InvalidImageData as err:
                raise ServiceValidationError(
                    "Invalid image data provided",
                    translation_domain=DOMAIN,
                    translation_key="invalid_imagedata",
                    translation_placeholders={"message": str(err)},
                ) from err
            self._check_path_is_allowed(notification_params)
        try:
            await self.notify.async_send(
                message, title=title, params=notification_params
            )
        except NotificationException as err:
            raise HomeAssistantError(err) from err
