"""Script to run benchmarks."""
import argparse
import asyncio
from contextlib import suppress
from datetime import datetime
import logging
from timeit import default_timer as timer
from typing import Callable, Dict, TypeVar

from homeassistant import core
from homeassistant.components.websocket_api.const import JSON_DUMP
from homeassistant.const import ATTR_NOW, EVENT_STATE_CHANGED, EVENT_TIME_CHANGED
from homeassistant.util import dt as dt_util

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs
# mypy: no-warn-return-any

CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)  # pylint: disable=invalid-name

BENCHMARKS: Dict[str, Callable] = {}


def run(args):
    """Handle benchmark commandline script."""
    # Disable logging
    logging.getLogger("homeassistant.core").setLevel(logging.CRITICAL)

    parser = argparse.ArgumentParser(description=("Run a Home Assistant benchmark."))
    parser.add_argument("name", choices=BENCHMARKS)
    parser.add_argument("--script", choices=["benchmark"])

    args = parser.parse_args()

    bench = BENCHMARKS[args.name]

    print("Using event loop:", asyncio.get_event_loop_policy().__module__)

    with suppress(KeyboardInterrupt):
        while True:
            loop = asyncio.new_event_loop()
            hass = core.HomeAssistant(loop)
            hass.async_stop_track_tasks()
            runtime = loop.run_until_complete(bench(hass))
            print(f"Benchmark {bench.__name__} done in {runtime}s")
            loop.run_until_complete(hass.async_stop())
            loop.close()


def benchmark(func: CALLABLE_T) -> CALLABLE_T:
    """Decorate to mark a benchmark."""
    BENCHMARKS[func.__name__] = func
    return func


@benchmark
async def fire_events(hass):
    """Fire a million events."""
    count = 0
    event_name = "benchmark_event"
    event = asyncio.Event()

    @core.callback
    def listener(_):
        """Handle event."""
        nonlocal count
        count += 1

        if count == 10 ** 6:
            event.set()

    hass.bus.async_listen(event_name, listener)

    for _ in range(10 ** 6):
        hass.bus.async_fire(event_name)

    start = timer()

    await event.wait()

    return timer() - start


@benchmark
async def time_changed_helper(hass):
    """Run a million events through time changed helper."""
    count = 0
    event = asyncio.Event()

    @core.callback
    def listener(_):
        """Handle event."""
        nonlocal count
        count += 1

        if count == 10 ** 6:
            event.set()

    hass.helpers.event.async_track_time_change(listener, minute=0, second=0)
    event_data = {ATTR_NOW: datetime(2017, 10, 10, 15, 0, 0, tzinfo=dt_util.UTC)}

    for _ in range(10 ** 6):
        hass.bus.async_fire(EVENT_TIME_CHANGED, event_data)

    start = timer()

    await event.wait()

    return timer() - start


@benchmark
async def state_changed_helper(hass):
    """Run a million events through state changed helper."""
    count = 0
    entity_id = "light.kitchen"
    event = asyncio.Event()

    @core.callback
    def listener(*args):
        """Handle event."""
        nonlocal count
        count += 1

        if count == 10 ** 6:
            event.set()

    hass.helpers.event.async_track_state_change(entity_id, listener, "off", "on")
    event_data = {
        "entity_id": entity_id,
        "old_state": core.State(entity_id, "off"),
        "new_state": core.State(entity_id, "on"),
    }

    for _ in range(10 ** 6):
        hass.bus.async_fire(EVENT_STATE_CHANGED, event_data)

    start = timer()

    await event.wait()

    return timer() - start


@benchmark
async def logbook_filtering_state(hass):
    """Filter state changes."""
    return await _logbook_filtering(hass, 1, 1)


@benchmark
async def logbook_filtering_attributes(hass):
    """Filter attribute changes."""
    return await _logbook_filtering(hass, 1, 2)


@benchmark
async def _logbook_filtering(hass, last_changed, last_updated):
    # pylint: disable=import-outside-toplevel
    from homeassistant.components import logbook

    entity_id = "test.entity"

    old_state = {"entity_id": entity_id, "state": "off"}

    new_state = {
        "entity_id": entity_id,
        "state": "on",
        "last_updated": last_updated,
        "last_changed": last_changed,
    }

    event = core.Event(
        EVENT_STATE_CHANGED,
        {"entity_id": entity_id, "old_state": old_state, "new_state": new_state},
    )

    def yield_events(event):
        # pylint: disable=protected-access
        entities_filter = logbook._generate_filter_from_config({})
        for _ in range(10 ** 5):
            if logbook._keep_event(hass, event, entities_filter):
                yield event

    start = timer()

    list(logbook.humanify(hass, yield_events(event)))

    return timer() - start


@benchmark
async def valid_entity_id(hass):
    """Run valid entity ID a million times."""
    start = timer()
    for _ in range(10 ** 6):
        core.valid_entity_id("light.kitchen")
    return timer() - start


@benchmark
async def json_serialize_states(hass):
    """Serialize million states with websocket default encoder."""
    states = [
        core.State("light.kitchen", "on", {"friendly_name": "Kitchen Lights"})
        for _ in range(10 ** 6)
    ]

    start = timer()
    JSON_DUMP(states)
    return timer() - start
