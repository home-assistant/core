"""CodSpeed benchmarks for the event bus and event helpers.

The event bus carries every state change, and ``async_track_state_change_event``
is the routing layer almost every automation, template and trigger sits on. A
regression in either is felt across the whole system.

Run locally with: ``pytest benchmarks --codspeed``.
"""

from collections.abc import Callable

import pytest
from pytest_codspeed import BenchmarkFixture

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event


@callback
def _noop(event: Event) -> None:
    """Do nothing, cheaply."""


def test_event_fire_no_listeners(
    benchmark: BenchmarkFixture, hass: HomeAssistant
) -> None:
    """Fire an event nobody listens to (the bare dispatch cost)."""
    benchmark(lambda: hass.bus.async_fire("benchmark_event", {"value": 1}))


@pytest.mark.parametrize("listeners", [1, 10])
def test_event_fire_callbacks(
    benchmark: BenchmarkFixture, hass: HomeAssistant, listeners: int
) -> None:
    """Fire an event with N callback listeners that run inline."""
    fired = 0

    @callback
    def listener(event: Event) -> None:
        nonlocal fired
        fired += 1

    for _ in range(listeners):
        hass.bus.async_listen("benchmark_event", listener)

    benchmark(lambda: hass.bus.async_fire("benchmark_event", {"value": 1}))

    assert fired


def test_event_fire_filtered_reject(
    benchmark: BenchmarkFixture, hass: HomeAssistant
) -> None:
    """Fire an event whose listener is gated out by an event_filter.

    The filter runs but the listener does not, so this isolates the filter
    short-circuit cost from the listener body.
    """

    @callback
    def event_filter(event_data: dict) -> bool:
        return False

    hass.bus.async_listen("benchmark_event", _noop, event_filter=event_filter)

    benchmark(lambda: hass.bus.async_fire("benchmark_event", {"value": 1}))


def test_state_change_tracked(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Fire a state change routed to a tracked entity's listener.

    This is the real automation hot path: ``async_set`` fires
    EVENT_STATE_CHANGED, the dispatcher does a dict lookup on the entity_id and
    runs the inline callback.
    """
    fired = 0

    @callback
    def listener(event: Event) -> None:
        nonlocal fired
        fired += 1

    async_track_state_change_event(hass, "sensor.tracked", listener)
    counter = 0

    def _set() -> None:
        nonlocal counter
        counter += 1
        hass.states.async_set("sensor.tracked", str(counter))

    benchmark(_set)

    assert fired


def test_state_change_untracked(
    benchmark: BenchmarkFixture, hass: HomeAssistant
) -> None:
    """Fire a state change for an entity nobody tracks (the dict-miss path).

    Tracking is installed for a different entity, so the dispatcher's lookup
    misses and returns fast. This is the common case on a busy bus.
    """
    async_track_state_change_event(hass, "sensor.tracked", _noop)
    counter = 0

    def _set() -> None:
        nonlocal counter
        counter += 1
        hass.states.async_set("sensor.untracked", str(counter))

    benchmark(_set)


@pytest.mark.parametrize("receivers", [0, 1, 10])
def test_dispatcher_send(
    benchmark: BenchmarkFixture, hass: HomeAssistant, receivers: int
) -> None:
    """Send a dispatcher signal to N connected receivers."""
    fired = 0

    @callback
    def receiver(*args: object) -> None:
        nonlocal fired
        fired += 1

    for _ in range(receivers):
        async_dispatcher_connect(hass, "benchmark_signal", receiver)

    benchmark(lambda: async_dispatcher_send(hass, "benchmark_signal", 1))


def test_call_later_schedule(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Schedule a delayed callback and cancel it (the timer-tracking cost).

    Cancelling inside the measured call keeps timers from piling up on the loop
    across iterations.
    """

    def _schedule() -> None:
        cancel: Callable[[], None] = async_call_later(hass, 60, _noop)
        cancel()

    benchmark(_schedule)
