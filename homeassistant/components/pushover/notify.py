"""Pushover platform for notify component."""

from __future__ import annotations

import logging
from typing import Any

from pushover_complete import BadAPIRequestError, PushoverAPI
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ATTACHMENT,
    ATTR_CALLBACK_URL,
    ATTR_EXPIRE,
    ATTR_HTML,
    ATTR_PRIORITY,
    ATTR_RETRY,
    ATTR_SOUND,
    ATTR_TAG,
    ATTR_TAGS,
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_URL,
    ATTR_URL_TITLE,
    CONF_USER_KEY,
    DOMAIN,
    SERVICE_CANCEL,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_CANCEL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TAG): cv.string,
    }
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> PushoverNotificationService | None:
    """Get the Pushover notification service."""
    if discovery_info is None:
        return None

    pushover_api: PushoverAPI = hass.data[DOMAIN][discovery_info["entry_id"]]
    entry_id: str = discovery_info["entry_id"]

    service = PushoverNotificationService(
        hass, pushover_api, discovery_info[CONF_USER_KEY], entry_id
    )

    # Store the service instance keyed by entry_id so the domain-level cancel
    # service can reach every config entry's instance independently.
    hass.data[DOMAIN].setdefault("services", {})[entry_id] = service

    # Register the cancel service once; skip if already registered by a
    # previous config entry.
    if not hass.services.has_service(DOMAIN, SERVICE_CANCEL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CANCEL,
            _async_cancel_service_handler,
            schema=SERVICE_CANCEL_SCHEMA,
        )

    return service


async def _async_cancel_service_handler(service: ServiceCall) -> None:
    """Cancel emergency notifications across all Pushover config entries."""
    tag: str = service.data.get(ATTR_TAG, "")
    instances: dict[str, PushoverNotificationService] = service.hass.data[DOMAIN].get(
        "services", {}
    )

    if not instances:
        _LOGGER.debug("No Pushover service instances registered; nothing to cancel")
        return

    for entry_id, instance in instances.items():
        _LOGGER.debug("Running cancel on entry %s (tag=%r)", entry_id, tag)
        await service.hass.async_add_executor_job(instance.cancel_by_tag, tag)


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(
        self,
        hass: HomeAssistant,
        pushover: PushoverAPI,
        user_key: str,
        entry_id: str,
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._user_key = user_key
        self.pushover = pushover
        self._entry_id = entry_id
        # Maps receipt id -> list of tags assigned when the message was sent.
        self._receipt_tags: dict[str, list[str]] = {}

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        # Extract params from data dict
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        url = data.get(ATTR_URL)
        url_title = data.get(ATTR_URL_TITLE)
        priority = data.get(ATTR_PRIORITY)
        retry = data.get(ATTR_RETRY)
        expire = data.get(ATTR_EXPIRE)
        ttl = data.get(ATTR_TTL)
        callback_url = data.get(ATTR_CALLBACK_URL)
        timestamp = data.get(ATTR_TIMESTAMP)
        sound = data.get(ATTR_SOUND)
        html = 1 if data.get(ATTR_HTML, False) else 0
        tags: list[str] = data.get(ATTR_TAGS, [])

        if isinstance(tags, str):
            tags = [tags]

        # Check for attachment
        if (image := data.get(ATTR_ATTACHMENT)) is not None:
            # Only allow attachments from whitelisted paths, check valid path
            if self._hass.config.is_allowed_path(data[ATTR_ATTACHMENT]):
                # try to open it as a normal file.
                try:
                    # pylint: disable-next=consider-using-with
                    file_handle = open(data[ATTR_ATTACHMENT], "rb")
                    # Replace the attachment identifier with file object.
                    image = file_handle
                except OSError as ex_val:
                    _LOGGER.error(ex_val)
                    # Remove attachment key to send without attachment.
                    image = None
            else:
                _LOGGER.error("Path is not whitelisted")
                # Remove attachment key to send without attachment.
                image = None

        try:
            result = self.pushover.send_message(
                user=self._user_key,
                message=message,
                device=",".join(kwargs.get(ATTR_TARGET, [])),
                title=title,
                url=url,
                url_title=url_title,
                image=image,
                priority=priority,
                retry=retry,
                expire=expire,
                callback_url=callback_url,
                timestamp=timestamp,
                sound=sound,
                html=html,
                ttl=ttl,
            )
        except BadAPIRequestError as err:
            raise HomeAssistantError(str(err)) from err

        if isinstance(result, dict) and "receipt" in result and tags:
            receipt: str = result["receipt"]
            self._receipt_tags[receipt] = tags
            _LOGGER.debug(
                "Entry %s: stored receipt %s with tags %s",
                self._entry_id,
                receipt,
                tags,
            )

    def cancel_by_tag(self, tag: str) -> None:
        """Cancel receipts matching tag, or all receipts when tag is empty.

        Called from the executor; blocking I/O is acceptable here.
        """
        if not self._receipt_tags:
            _LOGGER.debug("Entry %s: no receipts to cancel", self._entry_id)
            return

        if tag:
            receipts_to_cancel = [
                receipt
                for receipt, msg_tags in self._receipt_tags.items()
                if tag in msg_tags
            ]
            _LOGGER.debug(
                "Entry %s: cancelling receipts with tag %r: %s",
                self._entry_id,
                tag,
                receipts_to_cancel,
            )
        else:
            receipts_to_cancel = list(self._receipt_tags)
            _LOGGER.debug(
                "Entry %s: cancelling all receipts: %s",
                self._entry_id,
                receipts_to_cancel,
            )

        if not receipts_to_cancel:
            _LOGGER.debug("Entry %s: no receipts found for tag %r", self._entry_id, tag)
            return

        for receipt in receipts_to_cancel:
            try:
                self.pushover.cancel_receipt(receipt)
                _LOGGER.debug("Entry %s: cancelled receipt %s", self._entry_id, receipt)
            except BadAPIRequestError:
                _LOGGER.exception(
                    "Entry %s: failed to cancel receipt %s", self._entry_id, receipt
                )
            finally:
                self._receipt_tags.pop(receipt, None)
