"""Script to run benchmarks."""
import argparse
import asyncio
from contextlib import suppress
from datetime import datetime
import logging
from timeit import default_timer as timer

from homeassistant import core
from homeassistant.const import (
    ATTR_NOW, EVENT_STATE_CHANGED, EVENT_TIME_CHANGED)
from homeassistant.util import dt as dt_util

BENCHMARKS = {}


def run(args):
    """Handle ensure configuration commandline script."""
    # Disable logging
    logging.getLogger('homeassistant.core').setLevel(logging.CRITICAL)

    parser = argparse.ArgumentParser(
        description=("Run a Home Assistant benchmark."))
    parser.add_argument('name', choices=BENCHMARKS)
    parser.add_argument('--script', choices=['benchmark'])

    args = parser.parse_args()

    bench = BENCHMARKS[args.name]

    print('Using event loop:', asyncio.get_event_loop_policy().__module__)

    with suppress(KeyboardInterrupt):
        while True:
            loop = asyncio.new_event_loop()
            hass = core.HomeAssistant(loop)
            hass.async_stop_track_tasks()
            runtime = loop.run_until_complete(bench(hass))
            print('Benchmark {} done in {}s'.format(bench.__name__, runtime))
            loop.run_until_complete(hass.async_stop())
            loop.close()

    return 0


def benchmark(func):
    """Decorate to mark a benchmark."""
    BENCHMARKS[func.__name__] = func
    return func


@benchmark
@asyncio.coroutine
def async_million_events(hass):
    """Run a million events."""
    count = 0
    event_name = 'benchmark_event'
    event = asyncio.Event(loop=hass.loop)

    @core.callback
    def listener(_):
        """Handle event."""
        nonlocal count
        count += 1

        if count == 10**6:
            event.set()

    hass.bus.async_listen(event_name, listener)

    for _ in range(10**6):
        hass.bus.async_fire(event_name)

    start = timer()

    yield from event.wait()

    return timer() - start


@benchmark
@asyncio.coroutine
# pylint: disable=invalid-name
def async_million_time_changed_helper(hass):
    """Run a million events through time changed helper."""
    count = 0
    event = asyncio.Event(loop=hass.loop)

    @core.callback
    def listener(_):
        """Handle event."""
        nonlocal count
        count += 1

        if count == 10**6:
            event.set()

    hass.helpers.event.async_track_time_change(listener, minute=0, second=0)
    event_data = {
        ATTR_NOW: datetime(2017, 10, 10, 15, 0, 0, tzinfo=dt_util.UTC)
    }

    for _ in range(10**6):
        hass.bus.async_fire(EVENT_TIME_CHANGED, event_data)

    start = timer()

    yield from event.wait()

    return timer() - start


@benchmark
@asyncio.coroutine
# pylint: disable=invalid-name
def async_million_state_changed_helper(hass):
    """Run a million events through state changed helper."""
    count = 0
    entity_id = 'light.kitchen'
    event = asyncio.Event(loop=hass.loop)

    @core.callback
    def listener(*args):
        """Handle event."""
        nonlocal count
        count += 1

        if count == 10**6:
            event.set()

    hass.helpers.event.async_track_state_change(
        entity_id, listener, 'off', 'on')
    event_data = {
        'entity_id': entity_id,
        'old_state': core.State(entity_id, 'off'),
        'new_state': core.State(entity_id, 'on'),
    }

    for _ in range(10**6):
        hass.bus.async_fire(EVENT_STATE_CHANGED, event_data)

    start = timer()

    yield from event.wait()

    return timer() - start
