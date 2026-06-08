"""Live Activity push token resolution, storage and expiry cleanup."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import partial
from typing import Any

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from ..const import (
    ATTR_APP_DATA,
    ATTR_LIVE_ACTIVITY_EVENT,
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_LIVE_ACTIVITY_TOKEN,
    ATTR_LIVE_UPDATE,
    ATTR_PUSH_TO_START_LIVE_ACTIVITY_TOKEN,
    ATTR_TAG,
    ATTR_TOKEN,
    ATTR_WEBHOOK_ID,
    CLEAR_NOTIFICATION,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_STORE,
    DOMAIN,
    STORAGE_SAVE_DELAY_SECONDS,
)
from ..helpers import RemotePush, savable_state


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
) -> RemotePush:
    """Return remote notification data with any ActivityKit routing applied."""
    if not (resolved := resolve_live_activity_push(hass, registration, data)):
        return RemotePush(data=data)

    success_callback: Callable[[], None] | None = None
    if resolved.event is LiveActivityEvent.END:
        success_callback = partial(
            remove_live_activity_token,
            hass,
            registration[ATTR_WEBHOOK_ID],
            resolved.tag,
        )

    return RemotePush(
        data={
            **data,
            ATTR_LIVE_ACTIVITY_TOKEN: resolved.token,
            ATTR_DATA: {
                **(data.get(ATTR_DATA) or {}),
                ATTR_LIVE_ACTIVITY_EVENT: resolved.event,
            },
        },
        success_callback=success_callback,
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
        if stored_token_valid:
            return LiveActivityPush(stored[ATTR_TOKEN], LiveActivityEvent.END, tag)
        return None

    if not notification_data.get(ATTR_LIVE_UPDATE):
        return None

    if stored_token_valid:
        return LiveActivityPush(stored[ATTR_TOKEN], LiveActivityEvent.UPDATE, tag)

    if push_to_start := registration[ATTR_APP_DATA].get(
        ATTR_PUSH_TO_START_LIVE_ACTIVITY_TOKEN
    ):
        return LiveActivityPush(push_to_start, LiveActivityEvent.START, tag)

    return None


@callback
def store_live_activity_token(
    hass: HomeAssistant,
    webhook_id: str,
    activity_tag: str,
    token: str,
    expires_at: float,
) -> None:
    """Store a per-activity APNs token and start cleanup when needed."""
    live_activity_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    was_empty = not live_activity_tokens
    live_activity_tokens.setdefault(webhook_id, {})[activity_tag] = {
        ATTR_TOKEN: token,
        ATTR_LIVE_ACTIVITY_EXPIRES_AT: expires_at,
    }
    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
    if was_empty:
        async_schedule_next_cleanup(hass)


@callback
def remove_live_activity_token(
    hass: HomeAssistant, webhook_id: str, activity_tag: str
) -> bool:
    """Remove a stored Live Activity token, returning whether one existed."""
    live_activity_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]

    if webhook_id not in live_activity_tokens:
        return False

    device_tokens = live_activity_tokens[webhook_id]
    if device_tokens.pop(activity_tag, None) is None:
        return False

    if not device_tokens:
        del live_activity_tokens[webhook_id]

    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
    return True


@callback
def async_schedule_next_cleanup(hass: HomeAssistant) -> None:
    """Schedule a cleanup sweep for the earliest token expiry.

    Only call when no sweep is already scheduled, to keep a single timer in flight.
    """
    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    earliest_expires_at = min(
        (
            token[ATTR_LIVE_ACTIVITY_EXPIRES_AT]
            for device_tokens in tokens.values()
            for token in device_tokens.values()
        ),
        default=None,
    )
    if earliest_expires_at is None:
        return

    delay = max(0, earliest_expires_at - dt_util.utcnow().timestamp())

    async def run_cleanup(_now: datetime) -> None:
        await async_cleanup_expired_live_activity_tokens(hass)

    async_call_later(hass, delay, run_cleanup)


async def async_cleanup_expired_live_activity_tokens(hass: HomeAssistant) -> None:
    """Remove expired Live Activity tokens and reschedule the next sweep."""
    now = dt_util.utcnow().timestamp()
    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    changed = False

    for webhook_id in list(tokens):
        device_tokens = tokens[webhook_id]
        for tag, data in list(device_tokens.items()):
            if data[ATTR_LIVE_ACTIVITY_EXPIRES_AT] <= now:
                del device_tokens[tag]
                changed = True
        if not device_tokens:
            del tokens[webhook_id]
            changed = True

    if tokens:
        async_schedule_next_cleanup(hass)

    if changed:
        await hass.data[DOMAIN][DATA_STORE].async_save(savable_state(hass))
