"""Support for mobile_app push notifications."""

from __future__ import annotations

import asyncio
from functools import partial
from http import HTTPStatus
import logging
from typing import Any

import aiohttp

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
        async_add_entities([MobileAppNotifyEntity(entry)])


class MobileAppNotifyEntity(NotifyEntity):
    """Representation of a Mobile app notify entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "notify"
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the notify entity."""

        self._attr_unique_id = f"{entry.data[ATTR_DEVICE_ID]}_notify"
        self._attr_device_info = device_info(entry.data)
        self.entry = entry

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message via notify.send_message action."""
        await self._async_send_remote_message(message=message, title=title)

    async def _async_send_remote_message(
        self,
        message: str | None = None,
        title: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the push notification."""

        async def _send_message(data: dict[str, Any]):
            reg_info = {
                ATTR_APP_ID: self.entry.data[ATTR_APP_ID],
                ATTR_APP_VERSION: self.entry.data[ATTR_APP_VERSION],
                ATTR_WEBHOOK_ID: self.entry.data[ATTR_WEBHOOK_ID],
            }
            if ATTR_OS_VERSION in self.entry.data:
                reg_info[ATTR_OS_VERSION] = self.entry.data[ATTR_OS_VERSION]

            placeholders = {"device_name": self.entry.title}
            try:
                async with asyncio.timeout(10):
                    response = await async_get_clientsession(self.hass).post(
                        self.entry.data[ATTR_APP_DATA][ATTR_PUSH_URL],
                        json={
                            **data,
                            ATTR_PUSH_TOKEN: self.entry.data[ATTR_APP_DATA][
                                ATTR_PUSH_TOKEN
                            ],
                            "registration_info": reg_info,
                        },
                    )
                    result: dict[str, Any] = await response.json()

                log_rate_limits(self.hass, self.entry.title, result, logging.DEBUG)

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
                    message += (
                        " This message is generated externally to Home Assistant."
                    )
                _LOGGER.debug(
                    "Error sending notification to %s: %s", self.entry.title, message
                )

                if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="rate_limit_exceeded_sending_notification",
                        translation_placeholders=placeholders,
                    )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="error_sending_notification",
                    translation_placeholders=placeholders,
                )
            except TimeoutError as e:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="timeout_sending_notification",
                    translation_placeholders=placeholders,
                ) from e
            except aiohttp.ClientError as e:
                _LOGGER.debug(
                    "Error sending notification to %s:", self.entry.title, exc_info=True
                )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="error_sending_notification",
                    translation_placeholders=placeholders,
                ) from e

        data: dict[str, Any] = {}
        if message is not None:
            data[ATTR_MESSAGE] = message
        if title is not None:
            data[ATTR_TITLE] = title
        if kwargs:
            data[ATTR_DATA] = kwargs

        if (
            self.entry.data[ATTR_WEBHOOK_ID]
            in self.hass.data[DOMAIN][DATA_PUSH_CHANNEL]
        ):
            push_channel: PushChannel = self.hass.data[DOMAIN][DATA_PUSH_CHANNEL][
                self.entry.data[ATTR_WEBHOOK_ID]
            ]
            push_channel.async_send_notification(data, _send_message)
        elif ATTR_PUSH_URL in self.entry.data[ATTR_APP_DATA]:
            await _send_message(data)
        else:
            raise HomeAssistantError(
                f"Device {self.entry.title} not connected to local push notifications",
                translation_domain=DOMAIN,
                translation_key="device_not_connected_for_local_push_notifications",
                translation_placeholders={
                    "device_name": self.entry.data[ATTR_DEVICE_NAME]
                },
            )


def push_registrations(hass: HomeAssistant) -> dict[str, str]:
    """Return a dictionary of push enabled registrations."""
    targets = {}

    for webhook_id, entry in hass.data[DOMAIN][DATA_CONFIG_ENTRIES].items():
        if not supports_push(hass, webhook_id):
            continue

        targets[entry.data[ATTR_DEVICE_NAME]] = webhook_id

    return targets


def log_rate_limits(hass, device_name, resp, level=logging.INFO):
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

        local_push_channels = self.hass.data[DOMAIN][DATA_PUSH_CHANNEL]

        failed_targets = []
        for target in targets:
            registration = self.hass.data[DOMAIN][DATA_CONFIG_ENTRIES][target].data

            if target in local_push_channels:
                local_push_channels[target].async_send_notification(
                    data,
                    partial(
                        self._async_send_remote_message_target, target, registration
                    ),
                )
                continue

            # Test if local push only.
            if ATTR_PUSH_URL not in registration[ATTR_APP_DATA]:
                failed_targets.append(target)
                continue

            await self._async_send_remote_message_target(target, registration, data)

        if failed_targets:
            raise HomeAssistantError(
                f"Device(s) with webhook id(s) {', '.join(failed_targets)} not connected to local push notifications"
            )

    async def _async_send_remote_message_target(self, target, registration, data):
        """Send a message to a target."""
        app_data = registration[ATTR_APP_DATA]
        push_token = app_data[ATTR_PUSH_TOKEN]
        push_url = app_data[ATTR_PUSH_URL]

        target_data = dict(data)
        target_data[ATTR_PUSH_TOKEN] = push_token

        reg_info = {
            ATTR_APP_ID: registration[ATTR_APP_ID],
            ATTR_APP_VERSION: registration[ATTR_APP_VERSION],
            ATTR_WEBHOOK_ID: target,
        }
        if ATTR_OS_VERSION in registration:
            reg_info[ATTR_OS_VERSION] = registration[ATTR_OS_VERSION]

        target_data["registration_info"] = reg_info

        try:
            async with asyncio.timeout(10):
                response = await async_get_clientsession(self.hass).post(
                    push_url, json=target_data
                )
                result = await response.json()

            if response.status in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.ACCEPTED,
            ):
                log_rate_limits(self.hass, registration[ATTR_DEVICE_NAME], result)
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

            if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                _LOGGER.warning(message)
                log_rate_limits(
                    self.hass, registration[ATTR_DEVICE_NAME], result, logging.WARNING
                )
            else:
                _LOGGER.error(message)

        except TimeoutError:
            _LOGGER.error("Timeout sending notification to %s", push_url)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error sending notification to %s: %r", push_url, err)
