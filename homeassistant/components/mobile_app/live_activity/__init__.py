"""Live Activity push token resolution for outgoing notifications."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from functools import partial
from typing import Any

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    ATTR_APP_DATA,
    ATTR_LIVE_ACTIVITY_EVENT,
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_LIVE_ACTIVITY_START_FAILSAFE,
    ATTR_LIVE_ACTIVITY_TOKEN,
    ATTR_LIVE_UPDATE,
    ATTR_START_LIVE_ACTIVITY_TOKEN,
    ATTR_TAG,
    ATTR_TOKEN,
    ATTR_WEBHOOK_ID,
    CLEAR_NOTIFICATION,
    DATA_LIVE_ACTIVITY_TOKENS,
    DOMAIN,
)

# Imported so the webhook command registrations in the submodule run on import.
from . import webhook  # noqa: F401
from .store import (
    DEFAULT_START_FAILSAFE,
    buffer_pending_update,
    clear_start_pending,
    is_start_pending,
    mark_start_pending,
    remove_live_activity_token,
)


class LiveActivityEvent(StrEnum):
    """Apple ActivityKit lifecycle action for a Live Activity push."""

    START = "start"
    UPDATE = "update"
    END = "end"


@dataclass(slots=True)
class LiveActivityPush:
    """Resolved token routing data for an outgoing Live Activity push."""

    token: str
    event: LiveActivityEvent
    tag: str


def prepare_live_activity_remote_push(
    hass: HomeAssistant, registration: Mapping[str, Any], data: dict[str, Any]
) -> tuple[dict[str, Any] | None, CALLBACK_TYPE | None, CALLBACK_TYPE | None]:
    """Return remote notification data and optional on-success/on-failure callbacks.

    Applies any Live Activity routing. The data is ``None`` when the push should be dropped;
    a callback, when set, runs after the send succeeds or fails respectively.
    """
    if not (resolved := resolve_live_activity_push(hass, registration, data)):
        return data, None, None

    webhook_id = registration[ATTR_WEBHOOK_ID]
    success_callback: CALLBACK_TYPE | None = None
    failure_callback: CALLBACK_TYPE | None = None

    if resolved.event is LiveActivityEvent.START:
        # Token not reported yet, so an update has nothing to target. Send one start, then
        # buffer the latest update (flushed once the token arrives) instead of starting again.
        failsafe_seconds = registration[ATTR_APP_DATA].get(
            ATTR_LIVE_ACTIVITY_START_FAILSAFE
        )
        failsafe = (
            timedelta(seconds=failsafe_seconds)
            if failsafe_seconds
            else DEFAULT_START_FAILSAFE
        )
        if is_start_pending(hass, webhook_id, resolved.tag, failsafe):
            buffer_pending_update(hass, webhook_id, resolved.tag, data)
            return None, None, None
        mark_start_pending(hass, webhook_id, resolved.tag)
        # Mark eagerly so a concurrent start is suppressed, but roll back if the send fails so a
        # failed start is retried on the next update instead of buffered until the failsafe.
        failure_callback = partial(clear_start_pending, hass, webhook_id, resolved.tag)
    elif resolved.event is LiveActivityEvent.END:
        success_callback = partial(
            remove_live_activity_token, hass, webhook_id, resolved.tag
        )

    return (
        {
            **data,
            ATTR_LIVE_ACTIVITY_TOKEN: resolved.token,
            ATTR_DATA: {
                **(data.get(ATTR_DATA) or {}),
                ATTR_LIVE_ACTIVITY_EVENT: resolved.event,
            },
        },
        success_callback,
        failure_callback,
    )


def resolve_live_activity_push(
    hass: HomeAssistant, registration: Mapping[str, Any], data: dict[str, Any]
) -> LiveActivityPush | None:
    """Return Live Activity token routing data for a notification, or ``None``."""
    notification_data = data.get(ATTR_DATA) or {}
    tag = notification_data.get(ATTR_TAG)
    if not tag:
        return None

    webhook_id = registration[ATTR_WEBHOOK_ID]
    device_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS].get(webhook_id, {})
    stored = device_tokens.get(tag)
    stored_token_valid = (
        stored is not None
        and stored[ATTR_LIVE_ACTIVITY_EXPIRES_AT] > dt_util.utcnow().timestamp()
    )

    if data.get(ATTR_MESSAGE) == CLEAR_NOTIFICATION:
        # Clearing ends the cycle; release the start guard even if no token was ever reported.
        clear_start_pending(hass, webhook_id, tag)
        if stored_token_valid:
            return LiveActivityPush(stored[ATTR_TOKEN], LiveActivityEvent.END, tag)
        return None

    if not notification_data.get(ATTR_LIVE_UPDATE):
        return None

    if stored_token_valid:
        return LiveActivityPush(stored[ATTR_TOKEN], LiveActivityEvent.UPDATE, tag)

    if token := registration[ATTR_APP_DATA].get(ATTR_START_LIVE_ACTIVITY_TOKEN):
        return LiveActivityPush(token, LiveActivityEvent.START, tag)

    return None
