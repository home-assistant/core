"""Script to run benchmarks."""
from __future__ import annotations

import argparse
import asyncio
import collections
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
import json
import logging
from timeit import default_timer as timer
from typing import TypeVar

from homeassistant import core
from homeassistant.components.websocket_api.const import JSON_DUMP
from homeassistant.const import ATTR_NOW, EVENT_STATE_CHANGED, EVENT_TIME_CHANGED
from homeassistant.helpers.entityfilter import convert_include_exclude_filter
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util import dt as dt_util

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs
# mypy: no-warn-return-any

CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)  # pylint: disable=invalid-name

BENCHMARKS: dict[str, Callable] = {}


def run(args):
    """Handle benchmark commandline script."""
    # Disable logging
    logging.getLogger("homeassistant.core").setLevel(logging.CRITICAL)

    parser = argparse.ArgumentParser(description=("Run a Home Assistant benchmark."))
    parser.add_argument("name", choices=BENCHMARKS)
    parser.add_argument("--script", choices=["benchmark"])

    args = parser.parse_args()

    bench = BENCHMARKS[args.name]
    print("Using event loop:", asyncio.get_event_loop_policy().loop_name)

    with suppress(KeyboardInterrupt):
        while True:
            asyncio.run(run_benchmark(bench))


async def run_benchmark(bench):
    """Run a benchmark."""
    hass = core.HomeAssistant()
    runtime = await bench(hass)
    print(f"Benchmark {bench.__name__} done in {runtime}s")
    await hass.async_stop()


def benchmark(func: CALLABLE_T) -> CALLABLE_T:
    """Decorate to mark a benchmark."""
    BENCHMARKS[func.__name__] = func
    return func


@benchmark
async def fire_events(hass):
    """Fire a million events."""
    count = 0
    event_name = "benchmark_event"
    events_to_fire = 10 ** 6

    @core.callback
    def listener(_):
        """Handle event."""
        nonlocal count
        count += 1

    hass.bus.async_listen(event_name, listener)

    for _ in range(events_to_fire):
        hass.bus.async_fire(event_name)

    start = timer()

    await hass.async_block_till_done()

    assert count == events_to_fire

    return timer() - start


@benchmark
async def fire_events_with_filter(hass):
    """Fire a million events with a filter that rejects them."""
    count = 0
    event_name = "benchmark_event"
    events_to_fire = 10 ** 6

    @core.callback
    def event_filter(event):
        """Filter event."""
        return False

    @core.callback
    def listener(_):
        """Handle event."""
        nonlocal count
        count += 1

    hass.bus.async_listen(event_name, listener, event_filter=event_filter)

    for _ in range(events_to_fire):
        hass.bus.async_fire(event_name)

    start = timer()

    await hass.async_block_till_done()

    assert count == 0

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
    """Run a million events through state changed helper with 1000 entities."""
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

    for idx in range(1000):
        hass.helpers.event.async_track_state_change(
            f"{entity_id}{idx}", listener, "off", "on"
        )
    event_data = {
        "entity_id": f"{entity_id}0",
        "old_state": core.State(entity_id, "off"),
        "new_state": core.State(entity_id, "on"),
    }

    for _ in range(10 ** 6):
        hass.bus.async_fire(EVENT_STATE_CHANGED, event_data)

    start = timer()

    await event.wait()

    return timer() - start


@benchmark
async def state_changed_event_helper(hass):
    """Run a million events through state changed event helper with 1000 entities."""
    count = 0
    entity_id = "light.kitchen"
    events_to_fire = 10 ** 6

    @core.callback
    def listener(*args):
        """Handle event."""
        nonlocal count
        count += 1

    hass.helpers.event.async_track_state_change_event(
        [f"{entity_id}{idx}" for idx in range(1000)], listener
    )

    event_data = {
        "entity_id": f"{entity_id}0",
        "old_state": core.State(entity_id, "off"),
        "new_state": core.State(entity_id, "on"),
    }

    for _ in range(events_to_fire):
        hass.bus.async_fire(EVENT_STATE_CHANGED, event_data)

    start = timer()

    await hass.async_block_till_done()

    assert count == events_to_fire

    return timer() - start


@benchmark
async def state_changed_event_filter_helper(hass):
    """Run a million events through state changed event helper with 1000 entities that all get filtered."""
    count = 0
    entity_id = "light.kitchen"
    events_to_fire = 10 ** 6

    @core.callback
    def listener(*args):
        """Handle event."""
        nonlocal count
        count += 1

    hass.helpers.event.async_track_state_change_event(
        [f"{entity_id}{idx}" for idx in range(1000)], listener
    )

    event_data = {
        "entity_id": "switch.no_listeners",
        "old_state": core.State(entity_id, "off"),
        "new_state": core.State(entity_id, "on"),
    }

    for _ in range(events_to_fire):
        hass.bus.async_fire(EVENT_STATE_CHANGED, event_data)

    start = timer()

    await hass.async_block_till_done()

    assert count == 0

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

    event = _create_state_changed_event_from_old_new(
        entity_id, dt_util.utcnow(), old_state, new_state
    )

    entity_attr_cache = logbook.EntityAttributeCache(hass)

    entities_filter = convert_include_exclude_filter(
        logbook.INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA({})
    )

    def yield_events(event):
        for _ in range(10 ** 5):
            # pylint: disable=protected-access
            if logbook._keep_event(hass, event, entities_filter):
                yield event

    start = timer()

    list(logbook.humanify(hass, yield_events(event), entity_attr_cache, {}))

    return timer() - start


@benchmark
async def filtering_entity_id(hass):
    """Run a 100k state changes through entity filter."""
    config = {
        "include": {
            "domains": [
                "automation",
                "script",
                "group",
                "media_player",
                "custom_component",
            ],
            "entity_globs": [
                "binary_sensor.*_contact",
                "binary_sensor.*_occupancy",
                "binary_sensor.*_detected",
                "binary_sensor.*_active",
                "input_*",
                "device_tracker.*_phone",
                "switch.*_light",
                "binary_sensor.*_charging",
                "binary_sensor.*_lock",
                "binary_sensor.*_connected",
            ],
            "entities": [
                "test.entity_1",
                "test.entity_2",
                "binary_sensor.garage_door_open",
                "test.entity_3",
                "test.entity_4",
            ],
        },
        "exclude": {
            "domains": ["input_number"],
            "entity_globs": ["media_player.google_*", "group.all_*"],
            "entities": [],
        },
    }

    entity_ids = [
        "automation.home_arrival",
        "script.shut_off_house",
        "binary_sensor.garage_door_open",
        "binary_sensor.front_door_lock",
        "binary_sensor.kitchen_motion_sensor_occupancy",
        "switch.desk_lamp",
        "light.dining_room",
        "input_boolean.guest_staying_over",
        "person.eleanor_fant",
        "alert.issue_at_home",
        "calendar.eleanor_fant_s_calendar",
        "sun.sun",
    ]

    entities_filter = convert_include_exclude_filter(config)
    size = len(entity_ids)

    start = timer()

    for i in range(10 ** 5):
        entities_filter(entity_ids[i % size])

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


def _create_state_changed_event_from_old_new(
    entity_id, event_time_fired, old_state, new_state
):
    """Create a state changed event from a old and new state."""
    attributes = {}
    if new_state is not None:
        attributes = new_state.get("attributes")
    attributes_json = json.dumps(attributes, cls=JSONEncoder)
    if attributes_json == "null":
        attributes_json = "{}"
    row = collections.namedtuple(
        "Row",
        [
            "event_type"
            "event_data"
            "time_fired"
            "context_id"
            "context_user_id"
            "state"
            "entity_id"
            "domain"
            "attributes"
            "state_id",
            "old_state_id",
        ],
    )

    row.event_type = EVENT_STATE_CHANGED
    row.event_data = "{}"
    row.attributes = attributes_json
    row.time_fired = event_time_fired
    row.state = new_state and new_state.get("state")
    row.entity_id = entity_id
    row.domain = entity_id and core.split_entity_id(entity_id)[0]
    row.context_id = None
    row.context_user_id = None
    row.old_state_id = old_state and 1
    row.state_id = new_state and 1

    # pylint: disable=import-outside-toplevel
    from homeassistant.components import logbook

    return logbook.LazyEventPartialState(row)
