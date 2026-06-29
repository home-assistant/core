"""Live Activity token storage and expiry cleanup."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime, timedelta
from functools import partial

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from ..const import (
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_TOKEN,
    DATA_LIVE_ACTIVITY_CLEANUP_CANCEL,
    DATA_LIVE_ACTIVITY_PENDING_STARTS,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_STORE,
    DOMAIN,
    LIVE_ACTIVITY_START_COOLDOWN_SECONDS,
    STORAGE_SAVE_DELAY_SECONDS,
)
from ..helpers import savable_state


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
    live_activity_tokens.setdefault(webhook_id, {})[activity_tag] = {
        ATTR_TOKEN: token,
        ATTR_LIVE_ACTIVITY_EXPIRES_AT: expires_at,
    }
    clear_start_pending(hass, webhook_id, activity_tag)
    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
    async_schedule_next_cleanup(hass)


@callback
def remove_live_activity_token(
    hass: HomeAssistant, webhook_id: str, activity_tag: str
) -> None:
    """Remove a stored Live Activity token, returning whether one existed."""
    live_activity_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]

    clear_start_pending(hass, webhook_id, activity_tag)

    if (
        device_tokens := live_activity_tokens.get(webhook_id)
    ) is None or device_tokens.pop(activity_tag, None) is None:
        return

    if not device_tokens:
        del live_activity_tokens[webhook_id]

    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
    async_schedule_next_cleanup(hass)


@callback
def mark_start_pending(hass: HomeAssistant, webhook_id: str, activity_tag: str) -> None:
    """Record that a START push was just dispatched for this tag."""
    pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS]
    pending.setdefault(webhook_id, {})[activity_tag] = dt_util.utcnow()


@callback
def is_start_pending(hass: HomeAssistant, webhook_id: str, activity_tag: str) -> bool:
    """Return whether a START was dispatched within the cooldown window.

    The cooldown is released early when the device reports the per-activity
    token or when the activity is explicitly ended, so the window only matters
    when neither happens — typically a device that has stayed offline since
    the START was sent.
    """
    pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS]
    device_pending = pending.get(webhook_id)
    if device_pending is None or (sent_at := device_pending.get(activity_tag)) is None:
        return False
    if dt_util.utcnow() - sent_at < timedelta(
        seconds=LIVE_ACTIVITY_START_COOLDOWN_SECONDS
    ):
        return True
    clear_start_pending(hass, webhook_id, activity_tag)
    return False


@callback
def clear_start_pending(
    hass: HomeAssistant, webhook_id: str, activity_tag: str
) -> None:
    """Forget a pending START."""
    pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS]
    if (device_pending := pending.get(webhook_id)) is None:
        return
    device_pending.pop(activity_tag, None)
    if not device_pending:
        del pending[webhook_id]


@callback
def async_schedule_next_cleanup(hass: HomeAssistant) -> None:
    """Schedule a single cleanup sweep for the earliest token expiry.

    Cancels any previously scheduled sweep first, so calling this whenever the
    token set changes keeps exactly one timer in flight, set to the new earliest.
    """
    domain_data = hass.data[DOMAIN]
    if (cancel := domain_data[DATA_LIVE_ACTIVITY_CLEANUP_CANCEL]) is not None:
        cancel()
        domain_data[DATA_LIVE_ACTIVITY_CLEANUP_CANCEL] = None

    earliest_expires_at = min(
        (
            token[ATTR_LIVE_ACTIVITY_EXPIRES_AT]
            for device_tokens in domain_data[DATA_LIVE_ACTIVITY_TOKENS].values()
            for token in device_tokens.values()
        ),
        default=None,
    )
    if earliest_expires_at is None:
        return

    delay = max(0, earliest_expires_at - dt_util.utcnow().timestamp())

    async def run_cleanup(_now: datetime) -> None:
        domain_data[DATA_LIVE_ACTIVITY_CLEANUP_CANCEL] = None
        await async_cleanup_expired_live_activity_tokens(hass)

    domain_data[DATA_LIVE_ACTIVITY_CLEANUP_CANCEL] = async_call_later(
        hass, delay, run_cleanup
    )


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
