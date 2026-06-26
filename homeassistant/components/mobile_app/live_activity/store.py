"""Live Activity token storage and expiry cleanup."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from ..const import (
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    ATTR_TOKEN,
    DATA_LIVE_ACTIVITY_CLEANUP_CANCEL,
    DATA_LIVE_ACTIVITY_PENDING_STARTS,
    DATA_LIVE_ACTIVITY_PENDING_UPDATES,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_STORE,
    DOMAIN,
    STORAGE_SAVE_DELAY_SECONDS,
)
from ..helpers import savable_state

# Fallback when the device reports no failsafe of its own. Zero disables suppression, so a client
# that predates the failsafe field keeps its previous behavior until it ships the value.
DEFAULT_START_FAILSAFE = timedelta(seconds=0)


@callback
def store_live_activity_token(
    hass: HomeAssistant,
    webhook_id: str,
    activity_tag: str,
    token: str,
    expires_at: float,
) -> None:
    """Store a per-activity push token and start cleanup when needed."""
    device_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS].setdefault(
        webhook_id, {}
    )
    existing = device_tokens.get(activity_tag)
    if existing is not None and existing[ATTR_LIVE_ACTIVITY_EXPIRES_AT] > expires_at:
        # Reports can be delivered out of order; a later expiry means a newer token, so keep it.
        return
    # The token arriving acknowledges the start, so updates can now route to it.
    clear_start_pending(hass, webhook_id, activity_tag)
    device_tokens[activity_tag] = {
        ATTR_TOKEN: token,
        ATTR_LIVE_ACTIVITY_EXPIRES_AT: expires_at,
    }
    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
    async_schedule_next_cleanup(hass)


@callback
def remove_live_activity_token(
    hass: HomeAssistant, webhook_id: str, activity_tag: str
) -> None:
    """Remove a stored Live Activity token, returning whether one existed."""
    clear_start_pending(hass, webhook_id, activity_tag)
    live_activity_tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]

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
    """Record that a Live Activity start was just sent for this tag."""
    pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS]
    pending.setdefault(webhook_id, {})[activity_tag] = dt_util.utcnow()


@callback
def is_start_pending(
    hass: HomeAssistant, webhook_id: str, activity_tag: str, failsafe: timedelta
) -> bool:
    """Return whether a start for this tag was sent and is still awaiting its token."""
    device_pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS].get(
        webhook_id
    )
    if device_pending is None or (sent_at := device_pending.get(activity_tag)) is None:
        return False
    if dt_util.utcnow() - sent_at < failsafe:
        return True
    # Failsafe elapsed without a token; assume the start failed and allow a fresh one.
    clear_start_pending(hass, webhook_id, activity_tag)
    return False


@callback
def clear_start_pending(
    hass: HomeAssistant, webhook_id: str, activity_tag: str
) -> None:
    """Forget all pending state for a tag (token arrived, ended, cleared, or expired)."""
    # The buffered update shares the start guard's lifetime — drop it too.
    pop_pending_update(hass, webhook_id, activity_tag)
    device_pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS].get(
        webhook_id
    )
    if device_pending is None or device_pending.pop(activity_tag, None) is None:
        return
    if not device_pending:
        del hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS][webhook_id]


@callback
def buffer_pending_update(
    hass: HomeAssistant, webhook_id: str, activity_tag: str, data: dict[str, Any]
) -> None:
    """Buffer the latest update for a tag whose token has not been reported yet.

    Only the latest is kept; an update is a full state snapshot, so it supersedes earlier ones.
    """
    pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_UPDATES]
    pending.setdefault(webhook_id, {})[activity_tag] = data


@callback
def pop_pending_update(
    hass: HomeAssistant, webhook_id: str, activity_tag: str
) -> dict[str, Any] | None:
    """Remove and return the buffered update for a tag, if any."""
    device_pending = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_UPDATES].get(
        webhook_id
    )
    if device_pending is None:
        return None
    data = device_pending.pop(activity_tag, None)
    if not device_pending:
        del hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_UPDATES][webhook_id]
    return data


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
