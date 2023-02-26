"""Common test utils for working with recorder."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any, Literal, cast

from sqlalchemy import create_engine
from sqlalchemy.orm.session import Session

from homeassistant import core as ha
from homeassistant.components import recorder
from homeassistant.components.recorder import get_instance, statistics
from homeassistant.components.recorder.core import Recorder
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.components.recorder.tasks import RecorderTask, StatisticsTask
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.util import dt as dt_util

from . import db_schema_0

DEFAULT_PURGE_TASKS = 3


@dataclass
class BlockRecorderTask(RecorderTask):
    """A task to block the recorder for testing only."""

    event: asyncio.Event
    seconds: float

    def run(self, instance: Recorder) -> None:
        """Block the recorders event loop."""
        instance.hass.loop.call_soon_threadsafe(self.event.set)
        time.sleep(self.seconds)


async def async_block_recorder(hass: HomeAssistant, seconds: float) -> None:
    """Block the recorders event loop for testing.

    Returns as soon as the recorder has started the block.

    Does not wait for the block to finish.
    """
    event = asyncio.Event()
    get_instance(hass).queue_task(BlockRecorderTask(event, seconds))
    await event.wait()


def do_adhoc_statistics(hass: HomeAssistant, **kwargs: Any) -> None:
    """Trigger an adhoc statistics run."""
    if not (start := kwargs.get("start")):
        start = statistics.get_start_time()
    get_instance(hass).queue_task(StatisticsTask(start, False))


def wait_recording_done(hass: HomeAssistant) -> None:
    """Block till recording is done."""
    hass.block_till_done()
    trigger_db_commit(hass)
    hass.block_till_done()
    recorder.get_instance(hass).block_till_done()
    hass.block_till_done()


def trigger_db_commit(hass: HomeAssistant) -> None:
    """Force the recorder to commit."""
    recorder.get_instance(hass)._async_commit(dt_util.utcnow())


async def async_wait_recording_done(hass: HomeAssistant) -> None:
    """Async wait until recording is done."""
    await hass.async_block_till_done()
    async_trigger_db_commit(hass)
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass)
    await hass.async_block_till_done()


async def async_wait_purge_done(hass: HomeAssistant, max: int = None) -> None:
    """Wait for max number of purge events.

    Because a purge may insert another PurgeTask into
    the queue after the WaitTask finishes, we need up to
    a maximum number of WaitTasks that we will put into the
    queue.
    """
    if not max:
        max = DEFAULT_PURGE_TASKS
    for _ in range(max + 1):
        await async_wait_recording_done(hass)


@ha.callback
def async_trigger_db_commit(hass: HomeAssistant) -> None:
    """Force the recorder to commit. Async friendly."""
    recorder.get_instance(hass)._async_commit(dt_util.utcnow())


async def async_recorder_block_till_done(hass: HomeAssistant) -> None:
    """Non blocking version of recorder.block_till_done()."""
    await hass.async_add_executor_job(recorder.get_instance(hass).block_till_done)


def corrupt_db_file(test_db_file):
    """Corrupt an sqlite3 database file."""
    with open(test_db_file, "w+") as fhandle:
        fhandle.seek(200)
        fhandle.write("I am a corrupt db" * 100)


def create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    engine = create_engine(*args, **kwargs)
    db_schema_0.Base.metadata.create_all(engine)
    return engine


def run_information_with_session(
    session: Session, point_in_time: datetime | None = None
) -> RecorderRuns | None:
    """Return information about current run from the database."""
    recorder_runs = RecorderRuns

    query = session.query(recorder_runs)
    if point_in_time:
        query = query.filter(
            (recorder_runs.start < point_in_time) & (recorder_runs.end > point_in_time)
        )

    if (res := query.first()) is not None:
        session.expunge(res)
        return cast(RecorderRuns, res)
    return res


def statistics_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    statistic_ids: list[str] | None = None,
    period: Literal["5minute", "day", "hour", "week", "month"] = "hour",
    units: dict[str, str] | None = None,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]]
    | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Call statistics_during_period with defaults for simpler tests."""
    if types is None:
        types = {"last_reset", "max", "mean", "min", "state", "sum"}
    return statistics.statistics_during_period(
        hass, start_time, end_time, statistic_ids, period, units, types
    )


def assert_states_equal_without_context(state: State, other: State) -> None:
    """Assert that two states are equal, ignoring context."""
    assert_states_equal_without_context_and_last_changed(state, other)
    assert state.last_changed == other.last_changed


def assert_states_equal_without_context_and_last_changed(
    state: State, other: State
) -> None:
    """Assert that two states are equal, ignoring context and last_changed."""
    assert state.state == other.state
    assert state.attributes == other.attributes
    assert state.last_updated == other.last_updated


def assert_multiple_states_equal_without_context_and_last_changed(
    states: Iterable[State], others: Iterable[State]
) -> None:
    """Assert that multiple states are equal, ignoring context and last_changed."""
    states_list = list(states)
    others_list = list(others)
    assert len(states_list) == len(others_list)
    for i, state in enumerate(states_list):
        assert_states_equal_without_context_and_last_changed(state, others_list[i])


def assert_multiple_states_equal_without_context(
    states: Iterable[State], others: Iterable[State]
) -> None:
    """Assert that multiple states are equal, ignoring context."""
    states_list = list(states)
    others_list = list(others)
    assert len(states_list) == len(others_list)
    for i, state in enumerate(states_list):
        assert_states_equal_without_context(state, others_list[i])


def assert_events_equal_without_context(event: Event, other: Event) -> None:
    """Assert that two events are equal, ignoring context."""
    assert event.data == other.data
    assert event.event_type == other.event_type
    assert event.origin == other.origin
    assert event.time_fired == other.time_fired


def assert_dict_of_states_equal_without_context(
    states: dict[str, list[State]], others: dict[str, list[State]]
) -> None:
    """Assert that two dicts of states are equal, ignoring context."""
    assert len(states) == len(others)
    for entity_id, state in states.items():
        assert_multiple_states_equal_without_context(state, others[entity_id])


def assert_dict_of_states_equal_without_context_and_last_changed(
    states: dict[str, list[State]], others: dict[str, list[State]]
) -> None:
    """Assert that two dicts of states are equal, ignoring context and last_changed."""
    assert len(states) == len(others)
    for entity_id, state in states.items():
        assert_multiple_states_equal_without_context_and_last_changed(
            state, others[entity_id]
        )
