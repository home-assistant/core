"""Simplepush notification service."""

import logging
from typing import Any, override

from simplepush import ApiError, Client
from simplepush.legacy import BadRequest, UnknownError, send

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ATTACHMENTS,
    ATTR_EVENT,
    ATTR_LINKS,
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
    entry: ConfigEntry = discovery_info[CONF_ENTRY]
    service = SimplePushNotificationService(discovery_info)
    entry.async_on_unload(service.async_unregister_services)
    return service


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for Simplepush."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the Simplepush notification service."""
        self._client: Client | None = None
        self._topic: str | None = config.get(CONF_TOPIC)
        if CONF_API_TOKEN in config:
            self._client = Client(api_token=config[CONF_API_TOKEN])
            return
        self._device_key: str = config[CONF_DEVICE_KEY]
        self._event: str | None = config.get(CONF_EVENT)
        self._password: str | None = config.get(CONF_PASSWORD)
        self._salt: str | None = config.get(CONF_SALT)

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
        """Send a task through the current Simplepush app."""
        if data.get(ATTR_EVENT):
            _LOGGER.warning("Events are not supported by the Simplepush app")

        links = data.get(ATTR_LINKS, [])
        if isinstance(links, str):
            links = [links]
        if not (
            isinstance(links, list) and all(isinstance(link, str) for link in links)
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_links",
            )
        links = list(links)

        # The app tells images and videos apart by the URL, so the attachments
        # of the old app become plain links.
        attachments = data.get(ATTR_ATTACHMENTS)
        if isinstance(attachments, list):
            dropped = False
            for attachment in attachments:
                url = (
                    attachment.get("video") or attachment.get("image")
                    if isinstance(attachment, dict)
                    else None
                )
                if isinstance(url, str):
                    links.append(url)
                    dropped = dropped or "thumbnail" in attachment
                else:
                    dropped = True
            if dropped:
                _LOGGER.warning(
                    "Thumbnails and attachments without an image or video URL "
                    "are not supported by the Simplepush app and were not sent"
                )

        try:
            client.send_task(
                topic=self._topic,
                title=title,
                content=message,
                links=links or None,
            )
        except ApiError as err:
            if err.status == 401:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_api_token",
                ) from err
            if err.status in (403, 404):
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
