"""Simplepush notification service."""

from functools import partial
from http import HTTPStatus
import logging
from typing import Any, override

from simplepush import ApiError
from simplepush.legacy import BadRequest, UnknownError, send

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.const import CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import SimplePushConfigEntry
from .const import ATTR_ATTACHMENTS, ATTR_EVENT, CONF_DEVICE_KEY, CONF_SALT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SimplePushNotificationService | None:
    """Get the Simplepush notification service."""
    if discovery_info:
        return SimplePushNotificationService(discovery_info)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SimplePushConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entity of the current app."""
    async_add_entities([SimplePushNotifyEntity(entry)])


class SimplePushNotifyEntity(NotifyEntity):
    """Notify entity of the current Simplepush app."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: SimplePushConfigEntry) -> None:
        """Initialize the notify entity."""
        self._client = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Simplepush",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a task to your own devices."""
        try:
            await self.hass.async_add_executor_job(
                partial(
                    self._client.send_task,
                    title=title or ATTR_TITLE_DEFAULT,
                    content=message,
                )
            )
        except ApiError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_api_token",
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
            ) from err
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
            ) from err


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for Simplepush."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the Simplepush notification service."""
        self._device_key: str = config[CONF_DEVICE_KEY]
        self._event: str | None = config.get(CONF_EVENT)
        self._password: str | None = config.get(CONF_PASSWORD)
        self._salt: str | None = config.get(CONF_SALT)

    @override
    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a Simplepush user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        attachments = None
        # event can now be passed in the service data
        event = None
        if data := kwargs.get(ATTR_DATA):
            event = data.get(ATTR_EVENT)

            attachments_data = data.get(ATTR_ATTACHMENTS)
            if isinstance(attachments_data, list):
                attachments = []
                for attachment in attachments_data:
                    if not (
                        isinstance(attachment, dict)
                        and (
                            "image" in attachment
                            or "video" in attachment
                            or ("video" in attachment and "thumbnail" in attachment)
                        )
                    ):
                        _LOGGER.error("Attachment format is incorrect")
                        return

                    if "video" in attachment and "thumbnail" in attachment:
                        attachments.append(attachment)
                    elif "video" in attachment:
                        attachments.append(attachment["video"])
                    elif "image" in attachment:
                        attachments.append(attachment["image"])

        # use event from config until YAML config is removed
        event = event or self._event

        try:
            if self._password:
                send(
                    key=self._device_key,
                    password=self._password,
                    salt=self._salt,
                    title=title,
                    message=message,
                    attachments=attachments,
                    event=event,
                )
            else:
                send(
                    key=self._device_key,
                    title=title,
                    message=message,
                    attachments=attachments,
                    event=event,
                )

        except BadRequest as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="title_or_message_too_long",
            ) from err
        except UnknownError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
            ) from err
