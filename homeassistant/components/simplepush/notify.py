"""Simplepush notification service."""

from functools import partial
import logging
from typing import Any, override
from urllib.parse import urlparse

from simplepush import ApiError, Client
from simplepush.legacy import BadRequest, UnknownError, send

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
    migrate_notify_issue,
)
from homeassistant.const import CONF_API_TOKEN, CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import SimplePushConfigEntry
from .const import (
    ATTR_ATTACHMENTS,
    ATTR_EVENT,
    CONF_DEVICE_KEY,
    CONF_ENTRY,
    CONF_SALT,
    CONF_TOPIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SimplePushNotificationService | None:
    """Get the Simplepush notification service."""
    if not discovery_info:
        return None
    entry: SimplePushConfigEntry = discovery_info[CONF_ENTRY]
    service = SimplePushNotificationService(entry)
    entry.async_on_unload(service.async_unregister_services)
    return service


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SimplePushConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notify entity of the current app."""
    if CONF_API_TOKEN in entry.data:
        async_add_entities([SimplePushNotifyEntity(entry)])


def send_task(
    client: Client,
    topic: str | None,
    title: str,
    message: str,
    links: list[str] | None,
) -> None:
    """Send a task through the current Simplepush app."""
    try:
        client.send_task(topic=topic, title=title, content=message, links=links)
    except ApiError as err:
        if err.status == 401:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_api_token",
            ) from err
        if topic is not None and err.status in (403, 404):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="topic_not_joined",
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


class SimplePushNotifyEntity(NotifyEntity):
    """Notify entity of the current Simplepush app."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: SimplePushConfigEntry) -> None:
        """Initialize the notify entity."""
        self._client = entry.runtime_data
        self._topic: str | None = entry.data.get(CONF_TOPIC)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Simplepush",
            entry_type=DeviceEntryType.SERVICE,
        )

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a task to the devices of the entry."""
        await self.hass.async_add_executor_job(
            send_task,
            self._client,
            self._topic,
            title or ATTR_TITLE_DEFAULT,
            message,
            None,
        )


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for Simplepush."""

    def __init__(self, entry: SimplePushConfigEntry) -> None:
        """Initialize the Simplepush notification service."""
        config = entry.data
        self._client: Client | None = None
        self._topic: str | None = config.get(CONF_TOPIC)
        if CONF_API_TOKEN in config:
            self._client = entry.runtime_data
            return
        self._device_key: str = config[CONF_DEVICE_KEY]
        self._event: str | None = config.get(CONF_EVENT)
        self._password: str | None = config.get(CONF_PASSWORD)
        self._salt: str | None = config.get(CONF_SALT)

    @override
    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message, and ask moved entries to use the notify entity."""
        if self._client is not None:
            migrate_notify_issue(
                self.hass,
                DOMAIN,
                "Simplepush",
                "2027.4.0",
                service_name=self._service_name,
            )
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, **kwargs)
        )

    @override
    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a Simplepush user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if self._client is not None:
            self._send(self._client, title, message, kwargs.get(ATTR_DATA) or {})
            return

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

    def _send(
        self, client: Client, title: str, message: str, data: dict[str, Any]
    ) -> None:
        """Send a task with the old app's service data to the current app."""
        if data.get(ATTR_EVENT):
            _LOGGER.warning("Events are not supported by the Simplepush app")

        # The app tells images and videos apart by the URL, so the attachments
        # of the old app become plain links.
        links: list[str] = []
        attachments = data.get(ATTR_ATTACHMENTS)
        if isinstance(attachments, list):
            dropped = False
            for attachment in attachments:
                url = (
                    attachment.get("video") or attachment.get("image")
                    if isinstance(attachment, dict)
                    else None
                )
                if isinstance(url, str) and urlparse(url).scheme:
                    links.append(url)
                    dropped = dropped or "thumbnail" in attachment
                else:
                    dropped = True
            if dropped:
                _LOGGER.warning(
                    "Thumbnails and attachments without an image or video URL "
                    "are not supported by the Simplepush app and were not sent"
                )

        send_task(client, self._topic, title, message, links or None)
