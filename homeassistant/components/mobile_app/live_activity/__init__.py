"""Live Activity push token resolution for outgoing notifications."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Any

from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from ..const import (
    ATTR_APP_DATA,
    ATTR_LIVE_ACTIVITY_EVENT,
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
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
from .store import is_start_pending, mark_start_pending, remove_live_activity_token


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
) -> tuple[dict[str, Any], CALLBACK_TYPE | None]:
    """Return remote notification data and an optional on-success callback.

    Applies any Live Activity routing, the callback, when set, runs after a
    successful send. Raises ``HomeAssistantError`` when a START push for the
    same tag was dispatched within the cooldown window, since the device has
    not had time to report its per-activity token and a second START would
    spawn a duplicate Live Activity once the queued pushes deliver.
    """
    if not (resolved := resolve_live_activity_push(hass, registration, data)):
        return data, None

    webhook_id = registration[ATTR_WEBHOOK_ID]

    success_callback: CALLBACK_TYPE | None = None
    if resolved.event is LiveActivityEvent.END:
        success_callback = partial(
            remove_live_activity_token,
            hass,
            webhook_id,
            resolved.tag,
        )
    elif resolved.event is LiveActivityEvent.START:
        if is_start_pending(hass, webhook_id, resolved.tag):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="live_activity_start_already_pending",
                translation_placeholders={"tag": resolved.tag},
            )
        success_callback = partial(
            mark_start_pending,
            hass,
            webhook_id,
            resolved.tag,
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

    if token := registration[ATTR_APP_DATA].get(ATTR_START_LIVE_ACTIVITY_TOKEN):
        return LiveActivityPush(token, LiveActivityEvent.START, tag)

    return None
