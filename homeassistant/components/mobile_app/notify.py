"""Support for mobile_app push notifications."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_VERSION,
    ATTR_DEVICE_NAME,
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_LIVE_ACTIVITY_TAG,
    ATTR_LIVE_ACTIVITY_TOKEN,
    ATTR_LIVE_UPDATE,
    ATTR_OS_VERSION,
    ATTR_PUSH_RATE_LIMITS,
    ATTR_PUSH_RATE_LIMITS_ERRORS,
    ATTR_PUSH_RATE_LIMITS_MAXIMUM,
    ATTR_PUSH_RATE_LIMITS_RESETS_AT,
    ATTR_PUSH_RATE_LIMITS_SUCCESSFUL,
    ATTR_PUSH_TO_START_LIVE_ACTIVITY_TOKEN,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_TOKEN,
    ATTR_WEBHOOK_ID,
    CLEAR_NOTIFICATION,
    DATA_CONFIG_ENTRIES,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_NOTIFY,
    DATA_PUSH_CHANNEL,
    DATA_STORE,
    DOMAIN,
    SIGNAL_RECORD_NOTIFICATION,
    STORAGE_SAVE_DELAY_SECONDS,
)
from .helpers import device_info, savable_state
from .live_activity import LiveActivityEvent
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

        # Sends notification via local push if available
        # and fallback to cloud push if fails
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

    @callback
    def _async_handle_notification(self, webhook_id: str) -> None:
        """Handle notifications triggered externally."""
        if webhook_id == self._config_entry.data[ATTR_WEBHOOK_ID]:
            self._async_record_notification()

    async def async_added_to_hass(self) -> None:
        """Register callback."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RECORD_NOTIFICATION, self._async_handle_notification
            )
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
    resets_at = rate_limits[ATTR_PUSH_RATE_LIMITS_RESETS_AT]
    resets_at_time = dt_util.parse_datetime(resets_at) - dt_util.utcnow()
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
        str(resets_at_time).split(".", maxsplit=1)[0],
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
                async_dispatcher_send(self.hass, SIGNAL_RECORD_NOTIFICATION, target)
                continue

            # Test if local push only.
            if ATTR_PUSH_URL not in entry.data[ATTR_APP_DATA]:
                failed_targets.append(target)
                continue

            await self._async_send_remote_message_target(entry, data)
            async_dispatcher_send(self.hass, SIGNAL_RECORD_NOTIFICATION, target)

        if failed_targets:
            raise HomeAssistantError(
                "Device(s) with webhook id(s)"
                f" {', '.join(failed_targets)}"
                " not connected to local push notifications"
            )

    def _resolve_live_activity_push(
        self, entry: ConfigEntry, data: dict[str, Any]
    ) -> tuple[str, LiveActivityEvent] | None:
        """Return ``(token, event)`` for a Live Activity push, or ``None``.

        Core needs to choose the Apple ActivityKit route before calling the relay:
        updates and ends must use the stored per-activity token for the tag,
        while a new or expired tag must use the device's push-to-start token.
        """
        notification_data = data.get(ATTR_DATA) or {}
        tag = notification_data.get(ATTR_LIVE_ACTIVITY_TAG)
        if not tag:
            return None

        webhook_id = entry.data[ATTR_WEBHOOK_ID]
        device_tokens = self.hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS].get(
            webhook_id, {}
        )
        stored = device_tokens.get(tag)
        stored_token_valid = (
            stored is not None
            and stored[ATTR_LIVE_ACTIVITY_EXPIRES_AT] > dt_util.utcnow().timestamp()
        )

        # clear_notification ends a known activity; if no token is stored for
        # the tag, fall through to the normal clear_notification path.
        if data.get(ATTR_MESSAGE) == CLEAR_NOTIFICATION:
            if stored_token_valid:
                return stored[ATTR_TOKEN], LiveActivityEvent.END
            return None

        if not notification_data.get(ATTR_LIVE_UPDATE):
            return None

        if stored_token_valid:
            return stored[ATTR_TOKEN], LiveActivityEvent.UPDATE

        if push_to_start := entry.data[ATTR_APP_DATA].get(
            ATTR_PUSH_TO_START_LIVE_ACTIVITY_TOKEN
        ):
            return push_to_start, LiveActivityEvent.START

        return None

    async def _async_send_remote_message_target(
        self, entry: ConfigEntry, data: dict[str, Any]
    ) -> None:
        """Send a message to a target."""
        live_activity_token: str | None = None
        live_activity_event: LiveActivityEvent | None = None
        live_activity_tag: str | None = None
        if resolved := self._resolve_live_activity_push(entry, data):
            live_activity_token, live_activity_event = resolved
            live_activity_tag = (data.get(ATTR_DATA) or {}).get(ATTR_LIVE_ACTIVITY_TAG)
            data = {
                **data,
                ATTR_DATA: {
                    **(data.get(ATTR_DATA) or {}),
                    "event": live_activity_event,
                },
            }

        try:
            await _send_message(
                async_get_clientsession(self.hass),
                entry,
                data,
                live_activity_token=live_activity_token,
            )
        except HomeAssistantError as e:
            if e.translation_key == "rate_limit_exceeded_sending_notification":
                _LOGGER.warning(str(e))
            else:
                _LOGGER.error(str(e))
        else:
            if (
                live_activity_event == LiveActivityEvent.END
                and live_activity_tag is not None
            ):
                _remove_live_activity_token(self.hass, entry, live_activity_tag)


@callback
def _remove_live_activity_token(
    hass: HomeAssistant, entry: ConfigEntry, activity_tag: str
) -> None:
    """Remove a stored Live Activity token after Core sends an end event.

    Once the activity is ended, the per-activity token can no longer be used.
    Clearing it lets recurring automations reuse the same tag and start a new
    Live Activity with the device's push-to-start token.
    """
    webhook_id = entry.data[ATTR_WEBHOOK_ID]
    live_activity_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]

    if webhook_id not in live_activity_tokens:
        return

    device_tokens = live_activity_tokens[webhook_id]
    if device_tokens.pop(activity_tag, None) is None:
        return

    if not device_tokens:
        del live_activity_tokens[webhook_id]

    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )


async def _send_message(
    session: ClientSession,
    entry: ConfigEntry,
    data: dict[str, Any],
    *,
    live_activity_token: str | None = None,
) -> None:
    """Shared internal helper to send messages via cloud push notification services."""
    reg_info = {
        ATTR_APP_ID: entry.data[ATTR_APP_ID],
        ATTR_APP_VERSION: entry.data[ATTR_APP_VERSION],
        ATTR_WEBHOOK_ID: entry.data[ATTR_WEBHOOK_ID],
    }
    if ATTR_OS_VERSION in entry.data:
        reg_info[ATTR_OS_VERSION] = entry.data[ATTR_OS_VERSION]

    payload: dict[str, Any] = {
        **data,
        ATTR_PUSH_TOKEN: entry.data[ATTR_APP_DATA][ATTR_PUSH_TOKEN],
        "registration_info": reg_info,
    }
    if live_activity_token:
        payload[ATTR_LIVE_ACTIVITY_TOKEN] = live_activity_token

    try:
        async with asyncio.timeout(10):
            response = await session.post(
                entry.data[ATTR_APP_DATA][ATTR_PUSH_URL],
                json=payload,
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
