"""Live Activity push token lifecycle: expiry-driven cleanup loop."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import DATA_LIVE_ACTIVITY_TOKENS, DATA_STORE, DOMAIN
from .helpers import savable_state


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
            token["expires_at"]
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
    """Sweep expired tokens, keep the loop alive if any remain, save changes."""
    now = dt_util.utcnow().timestamp()
    tokens = hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    changed = False

    for webhook_id in list(tokens):
        device_tokens = tokens[webhook_id]
        for tag, data in list(device_tokens.items()):
            if data["expires_at"] <= now:
                del device_tokens[tag]
                changed = True
        if not device_tokens:
            del tokens[webhook_id]
            changed = True

    if tokens:
        async_schedule_next_cleanup(hass)

    if changed:
        await hass.data[DOMAIN][DATA_STORE].async_save(savable_state(hass))
