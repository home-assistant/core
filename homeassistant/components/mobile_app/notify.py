"""Support for mobile_app push notifications."""
# pylint: disable=hass-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from __future__ import annotations

import asyncio
from functools import partial
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_VERSION,
    ATTR_DEVICE_NAME,
    ATTR_OS_VERSION,
    ATTR_PUSH_RATE_LIMITS,
    ATTR_PUSH_RATE_LIMITS_ERRORS,
    ATTR_PUSH_RATE_LIMITS_MAXIMUM,
    ATTR_PUSH_RATE_LIMITS_RESETS_AT,
    ATTR_PUSH_RATE_LIMITS_SUCCESSFUL,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_WEBHOOK_ID,
    DATA_CONFIG_ENTRIES,
    DATA_NOTIFY,
    DATA_PUSH_CHANNEL,
    DOMAIN,
)
from .helpers import device_info
from .push_notification import PushChannel
from .util import supports_push

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mobile app notify platform."""
    if supports_push(hass, entry.data[ATTR_WEBHOOK_ID]):
        async_add_entities(
            [MobileAppNotifyEntity(entry, async_get_clientsession(hass))]
        )


class MobileAppNotifyEntity(NotifyEntity):
    """Representation of a Mobile app notify entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "notify"
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: ConfigEntry, session: ClientSession) -> None:
        """Initialize the notify entity."""

        self._attr_unique_id = entry.data[ATTR_DEVICE_ID]
        self._attr_device_info = device_info(entry.data)
        self._config_entry = entry
        self._session = session

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message via notify.send_message action."""

        data: dict[str, Any] = {}
        data[ATTR_MESSAGE] = message
        if title is not None:
            data[ATTR_TITLE] = title

        # Sends notification via local push if available and fallback to cloud push if fails
        if (webhook_id := self._config_entry.data[ATTR_WEBHOOK_ID]) in self.hass.data[
            DOMAIN
        ][DATA_PUSH_CHANNEL]:
            push_channel: PushChannel = self.hass.data[DOMAIN][DATA_PUSH_CHANNEL][
                webhook_id
            ]
            push_channel.async_send_notification(
                data,
                partial(_send_message, self._session, self._config_entry),
            )
        # Sends notification via cloud push notification service
        elif ATTR_PUSH_URL in self._config_entry.data[ATTR_APP_DATA]:
            await _send_message(self._session, self._config_entry, data)
        else:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_connected_for_local_push_notifications",
                translation_placeholders={"device_name": self._config_entry.title},
            )


def push_registrations(hass: HomeAssistant) -> dict[str, str]:
    """Return a dictionary of push enabled registrations."""
    targets = {}

    for webhook_id, entry in hass.data[DOMAIN][DATA_CONFIG_ENTRIES].items():
        if not supports_push(hass, webhook_id):
            continue

        targets[entry.data[ATTR_DEVICE_NAME]] = webhook_id

    return targets


def log_rate_limits(device_name, resp, level=logging.INFO):
    """Output rate limit log line at given level."""
    if ATTR_PUSH_RATE_LIMITS not in resp:
        return

    rate_limits = resp[ATTR_PUSH_RATE_LIMITS]
    resetsAt = rate_limits[ATTR_PUSH_RATE_LIMITS_RESETS_AT]
    resetsAtTime = dt_util.parse_datetime(resetsAt) - dt_util.utcnow()
    rate_limit_msg = (
        "mobile_app push notification rate limits for %s: "
        "%d sent, %d allowed, %d errors, "
        "resets in %s"
    )
    _LOGGER.log(
        level,
        rate_limit_msg,
        device_name,
        rate_limits[ATTR_PUSH_RATE_LIMITS_SUCCESSFUL],
        rate_limits[ATTR_PUSH_RATE_LIMITS_MAXIMUM],
        rate_limits[ATTR_PUSH_RATE_LIMITS_ERRORS],
        str(resetsAtTime).split(".", maxsplit=1)[0],
    )


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MobileAppNotificationService:
    """Get the mobile_app notification service."""
    service = hass.data[DOMAIN][DATA_NOTIFY] = MobileAppNotificationService()
    return service


class MobileAppNotificationService(BaseNotificationService):
    """Implement the notification service for mobile_app."""

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return push_registrations(self.hass)

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to the Lambda APNS gateway."""
        data = {ATTR_MESSAGE: message}

        # Remove default title from notifications.
        if (
            title_arg := kwargs.get(ATTR_TITLE)
        ) is not None and title_arg != ATTR_TITLE_DEFAULT:
            data[ATTR_TITLE] = title_arg
        if not (targets := kwargs.get(ATTR_TARGET)):
            targets = push_registrations(self.hass).values()

        if (data_arg := kwargs.get(ATTR_DATA)) is not None:
            data[ATTR_DATA] = data_arg

        local_push_channels: dict[str, PushChannel] = self.hass.data[DOMAIN][
            DATA_PUSH_CHANNEL
        ]

        failed_targets = []
        for target in targets:
            entry: ConfigEntry = self.hass.data[DOMAIN][DATA_CONFIG_ENTRIES][target]

            if target in local_push_channels:
                local_push_channels[target].async_send_notification(
                    data,
                    partial(self._async_send_remote_message_target, entry),
                )
                continue

            # Test if local push only.
            if ATTR_PUSH_URL not in entry.data[ATTR_APP_DATA]:
                failed_targets.append(target)
                continue

            await self._async_send_remote_message_target(entry, data)

        if failed_targets:
            raise HomeAssistantError(
                f"Device(s) with webhook id(s) {', '.join(failed_targets)} not connected to local push notifications"
            )

    async def _async_send_remote_message_target(
        self, entry: ConfigEntry, data: dict[str, Any]
    ):
        """Send a message to a target."""
        try:
            await _send_message(async_get_clientsession(self.hass), entry, data)
        except HomeAssistantError as e:
            if e.translation_key == "rate_limit_exceeded_sending_notification":
                _LOGGER.warning(str(e))
            else:
                _LOGGER.error(str(e))


async def _send_message(
    session: ClientSession, entry: ConfigEntry, data: dict[str, Any]
) -> None:
    """Shared internal helper to send messages via cloud push notification services."""
    reg_info = {
        ATTR_APP_ID: entry.data[ATTR_APP_ID],
        ATTR_APP_VERSION: entry.data[ATTR_APP_VERSION],
        ATTR_WEBHOOK_ID: entry.data[ATTR_WEBHOOK_ID],
    }
    if ATTR_OS_VERSION in entry.data:
        reg_info[ATTR_OS_VERSION] = entry.data[ATTR_OS_VERSION]

    try:
        async with asyncio.timeout(10):
            response = await session.post(
                entry.data[ATTR_APP_DATA][ATTR_PUSH_URL],
                json={
                    **data,
                    ATTR_PUSH_TOKEN: entry.data[ATTR_APP_DATA][ATTR_PUSH_TOKEN],
                    "registration_info": reg_info,
                },
            )
            result: dict[str, Any] = await response.json()

        log_rate_limits(entry.title, result, logging.DEBUG)

        if response.status in (
            HTTPStatus.OK,
            HTTPStatus.CREATED,
            HTTPStatus.ACCEPTED,
        ):
            return

        fallback_error = result.get("errorMessage", "Unknown error")
        fallback_message = (
            f"Internal server error, please try again later: {fallback_error}"
        )
        message = result.get("message", fallback_message)

        if "message" in result:
            if message[-1] not in [".", "?", "!"]:
                message += "."
            message += " This message is generated externally to Home Assistant."
        _LOGGER.debug("Error sending notification to %s: %s", entry.title, message)

        if response.status == HTTPStatus.TOO_MANY_REQUESTS:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limit_exceeded_sending_notification",
                translation_placeholders={"device_name": entry.title},
            )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="error_sending_notification",
            translation_placeholders={"device_name": entry.title},
        )
    except TimeoutError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_sending_notification",
            translation_placeholders={"device_name": entry.title},
        ) from e
    except ClientError as e:
        _LOGGER.debug(
            "Error sending notification to %s [%s]:",
            entry.title,
            entry.data[ATTR_APP_DATA][ATTR_PUSH_URL],
            exc_info=True,
        )
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="error_sending_notification",
            translation_placeholders={"device_name": entry.title},
        ) from e
