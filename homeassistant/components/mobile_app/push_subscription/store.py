"""Push-subscription storage, state tracking, and debounce.

A push subscription maps a push token to a set of entity_ids. The integration
owns the mapping and the state tracking; it has no knowledge of what the app
does with the resulting push.

State changes are debounced per subscription: a burst of rapid changes within
PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS collapses to a single push (trailing edge),
so a chatty entity does not exhaust the device's background-push budget.

Three runtime structures, all keyed [webhook_id][sub_id]:
- DATA_PUSH_SUBSCRIPTIONS: persisted token/entities/target mapping.
- DATA_PUSH_SUBSCRIPTION_UNSUBS: state-change listener cancels (runtime only).
- DATA_PUSH_SUBSCRIPTION_DEBOUNCE: pending debounce-timer cancels (runtime only).

Two lifecycle paths:
- async_teardown_device_subscriptions: on unload/reload, cancel listeners and
  pending timers but KEEP the stored mapping so it survives a restart.
- remove_stored_device_subscriptions: on entry removal, drop the mapping too.
"""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from collections.abc import Iterable
from datetime import datetime
from functools import partial
import logging

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from ..const import (
    ATTR_APP_DATA,
    ATTR_PUSH_URL,
    DATA_CONFIG_ENTRIES,
    DATA_PUSH_SUBSCRIPTION_DEBOUNCE,
    DATA_PUSH_SUBSCRIPTION_UNSUBS,
    DATA_PUSH_SUBSCRIPTIONS,
    DATA_STORE,
    DOMAIN,
    PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS,
    PUSH_SUBSCRIPTION_ENTITY_IDS,
    PUSH_SUBSCRIPTION_MAX_PER_DEVICE,
    PUSH_SUBSCRIPTION_TARGET,
    PUSH_SUBSCRIPTION_TOKEN,
    STORAGE_SAVE_DELAY_SECONDS,
)
from ..helpers import savable_state

_LOGGER = logging.getLogger(__name__)


@callback
def _async_cancel_debounce(hass: HomeAssistant, webhook_id: str, sub_id: str) -> None:
    """Cancel a pending debounce timer for one subscription, if present."""
    device_timers = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE].get(webhook_id)
    if device_timers and (cancel := device_timers.pop(sub_id, None)) is not None:
        cancel()
    if device_timers is not None and not device_timers:
        del hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE][webhook_id]


@callback
def _async_schedule_push(hass: HomeAssistant, webhook_id: str, sub_id: str) -> None:
    """Schedule a debounced push, resetting any in-flight timer.

    Trailing edge: each call restarts the clock, so the push only fires once the
    subscription has been quiet for PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS.
    """
    # Local import to avoid a circular import at module load.
    from .notify import async_send_subscription_push  # noqa: PLC0415

    _async_cancel_debounce(hass, webhook_id, sub_id)

    @callback
    def _fire(_now: datetime) -> None:
        # Clear our own timer handle first so cancel paths stay consistent.
        device_timers = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE].get(
            webhook_id
        )
        if device_timers is not None:
            device_timers.pop(sub_id, None)
            if not device_timers:
                del hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE][webhook_id]
        async_send_subscription_push(hass, webhook_id, sub_id)

    cancel = async_call_later(hass, PUSH_SUBSCRIPTION_DEBOUNCE_SECONDS, _fire)
    hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE].setdefault(webhook_id, {})[
        sub_id
    ] = cancel


@callback
def _async_unsub_tracker(hass: HomeAssistant, webhook_id: str, sub_id: str) -> None:
    """Cancel the state-change listener and any pending timer for one sub."""
    device_unsubs = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_UNSUBS].get(webhook_id)
    if device_unsubs and (unsub := device_unsubs.pop(sub_id, None)) is not None:
        unsub()
    if device_unsubs is not None and not device_unsubs:
        del hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_UNSUBS][webhook_id]
    _async_cancel_debounce(hass, webhook_id, sub_id)


@callback
def _async_setup_tracker(
    hass: HomeAssistant, webhook_id: str, sub_id: str, entity_ids: Iterable[str]
) -> None:
    """Start (or restart) the state-change listener for one subscription."""
    # Replace any existing listener so an updated entity set takes effect.
    _async_unsub_tracker(hass, webhook_id, sub_id)

    # Only arm a listener for registrations that can send a cloud push; others
    # would schedule a debounce timer on every state change that never sends.
    entry = hass.data[DOMAIN][DATA_CONFIG_ENTRIES].get(webhook_id)
    if entry is None or ATTR_PUSH_URL not in entry.data.get(ATTR_APP_DATA, {}):
        return

    @callback
    def _handle_state_change(event: Event[EventStateChangedData]) -> None:
        # Ignore changes fired while HA is still starting so a restart does not
        # push for every tracked entity as it is restored. Once running, every
        # change - including an entity first appearing (old_state is None) -
        # should refresh the subscribed surface.
        if not hass.is_running:
            return
        _async_schedule_push(hass, webhook_id, sub_id)

    unsub = async_track_state_change_event(hass, list(entity_ids), _handle_state_change)
    hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_UNSUBS].setdefault(webhook_id, {})[
        sub_id
    ] = unsub


@callback
def store_push_subscription(
    hass: HomeAssistant,
    webhook_id: str,
    sub_id: str,
    token: str,
    entity_ids: list[str],
    target: str | None,
) -> None:
    """Persist a subscription and (re)arm its state listener.

    The number of subscriptions retained per device is capped at
    PUSH_SUBSCRIPTION_MAX_PER_DEVICE; registering a new one past the cap evicts
    the oldest (FIFO), so the listener count a device can arm stays bounded.
    """
    device_subs = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS].setdefault(webhook_id, {})
    if (
        sub_id not in device_subs
        and len(device_subs) >= PUSH_SUBSCRIPTION_MAX_PER_DEVICE
    ):
        oldest_sub_id = next(iter(device_subs))
        _LOGGER.debug(
            "Push subscription cap reached for %s; evicting oldest %s",
            webhook_id,
            oldest_sub_id,
        )
        del device_subs[oldest_sub_id]
        _async_unsub_tracker(hass, webhook_id, oldest_sub_id)
    device_subs[sub_id] = {
        PUSH_SUBSCRIPTION_TOKEN: token,
        PUSH_SUBSCRIPTION_ENTITY_IDS: entity_ids,
        PUSH_SUBSCRIPTION_TARGET: target,
    }
    _async_setup_tracker(hass, webhook_id, sub_id, entity_ids)
    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )


@callback
def remove_push_subscription(hass: HomeAssistant, webhook_id: str, sub_id: str) -> None:
    """Remove one stored subscription and cancel its listener + timer."""
    subscriptions = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS]
    if (device_subs := subscriptions.get(webhook_id)) is None or device_subs.pop(
        sub_id, None
    ) is None:
        return
    if not device_subs:
        del subscriptions[webhook_id]

    _async_unsub_tracker(hass, webhook_id, sub_id)
    hass.data[DOMAIN][DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )


@callback
def async_teardown_device_subscriptions(hass: HomeAssistant, webhook_id: str) -> None:
    """Cancel all listeners + pending timers for a device on unload/reload.

    Keeps the stored mapping so the subscription is restored on next setup.
    """
    device_unsubs = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_UNSUBS].pop(
        webhook_id, None
    )
    if device_unsubs:
        for unsub in device_unsubs.values():
            unsub()
    device_timers = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTION_DEBOUNCE].pop(
        webhook_id, None
    )
    if device_timers:
        for cancel in device_timers.values():
            cancel()


@callback
def remove_stored_device_subscriptions(hass: HomeAssistant, webhook_id: str) -> None:
    """Drop all subscriptions for a device on entry removal."""
    hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS].pop(webhook_id, None)
    async_teardown_device_subscriptions(hass, webhook_id)


@callback
def async_restore_push_subscriptions(hass: HomeAssistant, webhook_id: str) -> None:
    """Re-arm listeners for one device's subscriptions after setup.

    Called from async_setup_entry once the entry is in DATA_CONFIG_ENTRIES, so a
    subscription survives a Home Assistant restart without the app re-registering.
    """
    if webhook_id not in hass.data[DOMAIN][DATA_CONFIG_ENTRIES]:
        return
    device_subs = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS].get(webhook_id, {})
    for sub_id, sub in device_subs.items():
        _async_setup_tracker(
            hass, webhook_id, sub_id, sub[PUSH_SUBSCRIPTION_ENTITY_IDS]
        )
