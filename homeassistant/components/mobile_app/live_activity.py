"""Live Activity push token lifecycle: expiry-driven cleanup loop."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime
from enum import StrEnum

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_LIVE_ACTIVITY_EXPIRES_AT,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_STORE,
    DOMAIN,
)
from .helpers import savable_state


class LiveActivityEvent(StrEnum):
    """Apple ActivityKit lifecycle action the relay should apply to a Live Activity push."""

    START = "start"
    UPDATE = "update"
    END = "end"


@callback
def async_schedule_next_cleanup(hass: HomeAssistant) -> None:
    """Schedule a sweep for the earliest token expiry.

    Only call when no sweep is already in flight. The invariant is: tokens
    non-empty ⟹ sweep scheduled. So the two safe call sites are (1) the
    webhook that added the first token (tokens was empty beforehand) and
    (2) the tail of a sweep that found surviving tokens (its own timer
    just fired).
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

    delay = earliest_expires_at - dt_util.utcnow().timestamp()

    async def run_cleanup(_now: datetime) -> None:
        await async_cleanup_expired_tokens(hass)

    async_call_later(hass, delay, run_cleanup)


async def async_cleanup_expired_tokens(hass: HomeAssistant) -> None:
    """Remove expired tokens and reschedule the next sweep at the earliest expiry.

    Runs as a one-shot callback scheduled by ``async_schedule_next_cleanup``. After
    sweeping, if any tokens remain it calls ``async_schedule_next_cleanup`` again to
    queue the next sweep — this self-rescheduling chain is what "the loop" refers to.
    When tokens are empty no further sweep is scheduled; the chain restarts the next
    time the webhook stores a token into an empty store.
    """
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
