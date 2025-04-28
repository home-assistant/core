"""The tests the History component."""

from __future__ import annotations

from collections.abc import Generator
from copy import copy
from datetime import datetime, timedelta
import json
from unittest.mock import patch, sentinel

from freezegun import freeze_time
import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder, history
from homeassistant.components.recorder.db_schema import (
    StateAttributes,
    States,
    StatesMeta,
)
from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util import dt as dt_util

from .common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    assert_multiple_states_equal_without_context,
    assert_multiple_states_equal_without_context_and_last_changed,
    assert_states_equal_without_context,
    async_recorder_block_till_done,
    async_wait_recording_done,
)

from tests.typing import RecorderInstanceContextManager


@pytest.fixture
def multiple_start_time_chunk_sizes(
    ids_for_start_time_chunk_sizes: int,
) -> Generator[None]:
    """Fixture to test different chunk sizes for start time query.

    Force the recorder to use different chunk sizes for start time query.

    In effect this forces get_significant_states_with_session
    to call _generate_significant_states_with_session_stmt multiple times.
    """
    with patch(
        "homeassistant.components.recorder.history.modern.MAX_IDS_FOR_INDEXED_GROUP_BY",
        ids_for_start_time_chunk_sizes,
    ):
        yield


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@pytest.fixture(autouse=True)
def setup_recorder(recorder_mock: Recorder) -> recorder.Recorder:
    """Set up recorder."""


async def test_get_full_significant_states_with_session_entity_no_matches(
    hass: HomeAssistant,
) -> None:
    """Test getting states at a specific point in time for entities that never have been recorded."""
    now = dt_util.utcnow()
    time_before_recorder_ran = now - timedelta(days=1000)
    with session_scope(hass=hass, read_only=True) as session:
        assert (
            history.get_full_significant_states_with_session(
                hass, session, time_before_recorder_ran, now, entity_ids=["demo.id"]
            )
            == {}
        )
        assert (
            history.get_full_significant_states_with_session(
                hass,
                session,
                time_before_recorder_ran,
                now,
                entity_ids=["demo.id", "demo.id2"],
            )
            == {}
        )


async def test_significant_states_with_session_entity_minimal_response_no_matches(
    hass: HomeAssistant,
) -> None:
    """Test getting states at a specific point in time for entities that never have been recorded."""
    now = dt_util.utcnow()
    time_before_recorder_ran = now - timedelta(days=1000)
    with session_scope(hass=hass, read_only=True) as session:
        assert (
            history.get_significant_states_with_session(
                hass,
                session,
                time_before_recorder_ran,
                now,
                entity_ids=["demo.id"],
                minimal_response=True,
            )
            == {}
        )
        assert (
            history.get_significant_states_with_session(
                hass,
                session,
                time_before_recorder_ran,
                now,
                entity_ids=["demo.id", "demo.id2"],
                minimal_response=True,
            )
            == {}
        )


async def test_significant_states_with_session_single_entity(
    hass: HomeAssistant,
) -> None:
    """Test get_significant_states_with_session with a single entity."""
    hass.states.async_set("demo.id", "any", {"attr": True})
    hass.states.async_set("demo.id", "any2", {"attr": True})
    await async_wait_recording_done(hass)
    now = dt_util.utcnow()
    with session_scope(hass=hass, read_only=True) as session:
        states = history.get_significant_states_with_session(
            hass,
            session,
            now - timedelta(days=1),
            now,
            entity_ids=["demo.id"],
            minimal_response=False,
        )
        assert len(states["demo.id"]) == 2


@pytest.mark.parametrize(
    ("attributes", "no_attributes", "limit"),
    [
        ({"attr": True}, False, 5000),
        ({}, True, 5000),
        ({"attr": True}, False, 3),
        ({}, True, 3),
    ],
)
async def test_state_changes_during_period(
    hass: HomeAssistant, attributes, no_attributes, limit
) -> None:
    """Test state change during period."""
    entity_id = "media_player.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state, attributes)
        return hass.states.get(entity_id)

    start = dt_util.utcnow()
    point = start + timedelta(seconds=1)
    end = point + timedelta(seconds=1)

    with freeze_time(start) as freezer:
        set_state("idle")
        set_state("YouTube")

        freezer.move_to(point)
        states = [
            set_state("idle"),
            set_state("Netflix"),
            set_state("Plex"),
            set_state("YouTube"),
        ]

        freezer.move_to(end)
        set_state("Netflix")
        set_state("Plex")
    await async_wait_recording_done(hass)

    hist = history.state_changes_during_period(
        hass, start, end, entity_id, no_attributes, limit=limit
    )

    assert_multiple_states_equal_without_context(states[:limit], hist[entity_id])


async def test_state_changes_during_period_last_reported(
    hass: HomeAssistant,
) -> None:
    """Test state change during period."""
    entity_id = "media_player.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state)
        return hass.states.get(entity_id)

    start = dt_util.utcnow()
    point1 = start + timedelta(seconds=1)
    point2 = point1 + timedelta(seconds=1)
    end = point2 + timedelta(seconds=1)

    with freeze_time(start) as freezer:
        set_state("idle")

        freezer.move_to(point1)
        set_state("YouTube")

        freezer.move_to(point2)
        states = [set_state("YouTube")]

        freezer.move_to(end)
        set_state("Netflix")
    await async_wait_recording_done(hass)

    hist = history.state_changes_during_period(hass, start, end, entity_id)

    assert_multiple_states_equal_without_context(states, hist[entity_id])


async def test_state_changes_during_period_descending(
    hass: HomeAssistant,
) -> None:
    """Test state change during period descending."""
    entity_id = "media_player.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state, {"any": 1})
        return hass.states.get(entity_id)

    start = dt_util.utcnow().replace(microsecond=0)
    point = start + timedelta(seconds=1)
    point2 = start + timedelta(seconds=1, microseconds=100)
    point3 = start + timedelta(seconds=1, microseconds=200)
    point4 = start + timedelta(seconds=1, microseconds=300)
    end = point + timedelta(seconds=1, microseconds=400)

    with freeze_time(start) as freezer:
        set_state("idle")
        set_state("YouTube")

        freezer.move_to(point)
        states = [set_state("idle")]

        freezer.move_to(point2)
        states.append(set_state("Netflix"))

        freezer.move_to(point3)
        states.append(set_state("Plex"))

        freezer.move_to(point4)
        states.append(set_state("YouTube"))

        freezer.move_to(end)
        set_state("Netflix")
        set_state("Plex")
    await async_wait_recording_done(hass)

    hist = history.state_changes_during_period(
        hass, start, end, entity_id, no_attributes=False, descending=False
    )

    assert_multiple_states_equal_without_context(states, hist[entity_id])

    hist = history.state_changes_during_period(
        hass, start, end, entity_id, no_attributes=False, descending=True
    )
    assert_multiple_states_equal_without_context(
        states, list(reversed(list(hist[entity_id])))
    )

    start_time = point2 + timedelta(microseconds=10)
    hist = history.state_changes_during_period(
        hass,
        start_time,  # Pick a point where we will generate a start time state
        end,
        entity_id,
        no_attributes=False,
        descending=True,
        include_start_time_state=True,
    )
    hist_states = list(hist[entity_id])
    assert hist_states[-1].last_updated == start_time
    assert hist_states[-1].last_changed == start_time
    assert len(hist_states) == 3
    # Make sure they are in descending order
    assert (
        hist_states[0].last_updated
        > hist_states[1].last_updated
        > hist_states[2].last_updated
    )
    assert (
        hist_states[0].last_changed
        > hist_states[1].last_changed
        > hist_states[2].last_changed
    )
    hist = history.state_changes_during_period(
        hass,
        start_time,  # Pick a point where we will generate a start time state
        end,
        entity_id,
        no_attributes=False,
        descending=False,
        include_start_time_state=True,
    )
    hist_states = list(hist[entity_id])
    assert hist_states[0].last_updated == start_time
    assert hist_states[0].last_changed == start_time
    assert len(hist_states) == 3
    # Make sure they are in ascending order
    assert (
        hist_states[0].last_updated
        < hist_states[1].last_updated
        < hist_states[2].last_updated
    )
    assert (
        hist_states[0].last_changed
        < hist_states[1].last_changed
        < hist_states[2].last_changed
    )


async def test_get_last_state_changes(hass: HomeAssistant) -> None:
    """Test number of state changes."""
    entity_id = "sensor.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=2)
    point = start + timedelta(minutes=1)
    point2 = point + timedelta(minutes=1, seconds=1)
    states = []

    with freeze_time(start) as freezer:
        set_state("1")

        freezer.move_to(point)
        states.append(set_state("2"))

        freezer.move_to(point2)
        states.append(set_state("3"))
    await async_wait_recording_done(hass)

    hist = history.get_last_state_changes(hass, 2, entity_id)

    assert_multiple_states_equal_without_context(states, hist[entity_id])


async def test_get_last_state_changes_last_reported(
    hass: HomeAssistant,
) -> None:
    """Test number of state changes."""
    entity_id = "sensor.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=2)
    point = start + timedelta(minutes=1)
    point2 = point + timedelta(minutes=1, seconds=1)
    states = []

    with freeze_time(start) as freezer:
        set_state("1")

        freezer.move_to(point)
        states.append(set_state("1"))

        freezer.move_to(point2)
        states.append(set_state("2"))
    await async_wait_recording_done(hass)

    hist = history.get_last_state_changes(hass, 2, entity_id)

    assert_multiple_states_equal_without_context(states, hist[entity_id])


async def test_get_last_state_change(hass: HomeAssistant) -> None:
    """Test getting the last state change for an entity."""
    entity_id = "sensor.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=2)
    point = start + timedelta(minutes=1)
    point2 = point + timedelta(minutes=1, seconds=1)
    states = []

    with freeze_time(start) as freezer:
        set_state("1")

        freezer.move_to(point)
        set_state("2")

        freezer.move_to(point2)
        states.append(set_state("3"))
    await async_wait_recording_done(hass)

    hist = history.get_last_state_changes(hass, 1, entity_id)

    assert_multiple_states_equal_without_context(states, hist[entity_id])


async def test_ensure_state_can_be_copied(
    hass: HomeAssistant,
) -> None:
    """Ensure a state can pass though copy().

    The filter integration uses copy() on states
    from history.
    """
    entity_id = "sensor.test"

    def set_state(state):
        """Set the state."""
        hass.states.async_set(entity_id, state)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=2)
    point = start + timedelta(minutes=1)

    with freeze_time(start) as freezer:
        set_state("1")

        freezer.move_to(point)
        set_state("2")
    await async_wait_recording_done(hass)

    hist = history.get_last_state_changes(hass, 2, entity_id)

    assert_states_equal_without_context(copy(hist[entity_id][0]), hist[entity_id][0])
    assert_states_equal_without_context(copy(hist[entity_id][1]), hist[entity_id][1])


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
async def test_get_significant_states(hass: HomeAssistant) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = record_states(hass)
    await async_wait_recording_done(hass)

    hist = history.get_significant_states(hass, zero, four, entity_ids=list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
async def test_get_significant_states_minimal_response(
    hass: HomeAssistant,
) -> None:
    """Test that only significant states are returned.

    When minimal responses is set only the first and
    last states return a complete state.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = record_states(hass)
    await async_wait_recording_done(hass)

    hist = history.get_significant_states(
        hass, zero, four, minimal_response=True, entity_ids=list(states)
    )
    entites_with_reducable_states = [
        "media_player.test",
        "media_player.test3",
    ]

    # All states for media_player.test state are reduced
    # down to last_changed and state when minimal_response
    # is set except for the first state.
    # is set.  We use JSONEncoder to make sure that are
    # pre-encoded last_changed is always the same as what
    # will happen with encoding a native state
    for entity_id in entites_with_reducable_states:
        entity_states = states[entity_id]
        for state_idx in range(1, len(entity_states)):
            input_state = entity_states[state_idx]
            orig_last_changed = json.dumps(
                process_timestamp(input_state.last_changed),
                cls=JSONEncoder,
            ).replace('"', "")
            orig_state = input_state.state
            entity_states[state_idx] = {
                "last_changed": orig_last_changed,
                "state": orig_state,
            }

    assert len(hist) == len(states)
    assert_states_equal_without_context(
        states["media_player.test"][0], hist["media_player.test"][0]
    )
    assert states["media_player.test"][1] == hist["media_player.test"][1]
    assert states["media_player.test"][2] == hist["media_player.test"][2]

    assert_multiple_states_equal_without_context(
        states["media_player.test2"], hist["media_player.test2"]
    )
    assert_states_equal_without_context(
        states["media_player.test3"][0], hist["media_player.test3"][0]
    )
    assert states["media_player.test3"][1] == hist["media_player.test3"][1]

    assert_multiple_states_equal_without_context(
        states["script.can_cancel_this_one"], hist["script.can_cancel_this_one"]
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        states["thermostat.test"], hist["thermostat.test"]
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        states["thermostat.test2"], hist["thermostat.test2"]
    )


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
@pytest.mark.parametrize("time_zone", ["Europe/Berlin", "US/Hawaii", "UTC"])
async def test_get_significant_states_with_initial(
    time_zone, hass: HomeAssistant
) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    await hass.config.async_set_time_zone(time_zone)
    zero, four, states = record_states(hass)
    await async_wait_recording_done(hass)

    one_and_half = zero + timedelta(seconds=1.5)
    for entity_id in states:
        if entity_id == "media_player.test":
            states[entity_id] = states[entity_id][1:]
        for state in states[entity_id]:
            # If the state is recorded before the start time
            # start it will have its last_updated and last_changed
            # set to the start time.
            if state.last_updated < one_and_half:
                state.last_updated = one_and_half
                state.last_changed = one_and_half

    hist = history.get_significant_states(
        hass, one_and_half, four, include_start_time_state=True, entity_ids=list(states)
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
async def test_get_significant_states_without_initial(
    hass: HomeAssistant,
) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = record_states(hass)
    await async_wait_recording_done(hass)

    one = zero + timedelta(seconds=1)
    one_with_microsecond = zero + timedelta(seconds=1, microseconds=1)
    one_and_half = zero + timedelta(seconds=1.5)
    for entity_id in states:
        states[entity_id] = [
            s
            for s in states[entity_id]
            if s.last_changed not in (one, one_with_microsecond)
        ]
    del states["media_player.test2"]
    del states["thermostat.test3"]

    hist = history.get_significant_states(
        hass,
        one_and_half,
        four,
        include_start_time_state=False,
        entity_ids=list(states),
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
async def test_get_significant_states_entity_id(
    hass: HomeAssistant,
) -> None:
    """Test that only significant states are returned for one entity."""
    zero, four, states = record_states(hass)
    await async_wait_recording_done(hass)

    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["thermostat.test3"]
    del states["script.can_cancel_this_one"]

    hist = history.get_significant_states(hass, zero, four, ["media_player.test"])
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


@pytest.mark.usefixtures("multiple_start_time_chunk_sizes")
async def test_get_significant_states_multiple_entity_ids(
    hass: HomeAssistant,
) -> None:
    """Test that only significant states are returned for one entity."""
    zero, four, states = record_states(hass)
    await async_wait_recording_done(hass)

    hist = history.get_significant_states(
        hass,
        zero,
        four,
        ["media_player.test", "thermostat.test"],
    )

    assert_multiple_states_equal_without_context_and_last_changed(
        states["media_player.test"], hist["media_player.test"]
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        states["thermostat.test"], hist["thermostat.test"]
    )


async def test_get_significant_states_are_ordered(
    hass: HomeAssistant,
) -> None:
    """Test order of results from get_significant_states.

    When entity ids are given, the results should be returned with the data
    in the same order.
    """
    zero, four, _states = record_states(hass)
    await async_wait_recording_done(hass)

    entity_ids = ["media_player.test", "media_player.test2"]
    hist = history.get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids
    entity_ids = ["media_player.test2", "media_player.test"]
    hist = history.get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids


async def test_get_significant_states_only(
    hass: HomeAssistant,
) -> None:
    """Test significant states when significant_states_only is set."""
    entity_id = "sensor.test"

    def set_state(state, **kwargs):
        """Set the state."""
        hass.states.async_set(entity_id, state, **kwargs)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=4)
    points = [start + timedelta(minutes=i) for i in range(1, 4)]

    states = []
    with freeze_time(start) as freezer:
        set_state("123", attributes={"attribute": 10.64})

        freezer.move_to(points[0])
        # Attributes are different, state not
        states.append(set_state("123", attributes={"attribute": 21.42}))

        freezer.move_to(points[1])
        # state is different, attributes not
        states.append(set_state("32", attributes={"attribute": 21.42}))

        freezer.move_to(points[2])
        # everything is different
        states.append(set_state("412", attributes={"attribute": 54.23}))
    await async_wait_recording_done(hass)

    hist = history.get_significant_states(
        hass,
        start,
        significant_changes_only=True,
        entity_ids=list({state.entity_id for state in states}),
    )

    assert len(hist[entity_id]) == 2
    assert not any(
        state.last_updated == states[0].last_updated for state in hist[entity_id]
    )
    assert any(
        state.last_updated == states[1].last_updated for state in hist[entity_id]
    )
    assert any(
        state.last_updated == states[2].last_updated for state in hist[entity_id]
    )

    hist = history.get_significant_states(
        hass,
        start,
        significant_changes_only=False,
        entity_ids=list({state.entity_id for state in states}),
    )

    assert len(hist[entity_id]) == 3
    assert_multiple_states_equal_without_context_and_last_changed(
        states, hist[entity_id]
    )


async def test_get_significant_states_only_minimal_response(
    hass: HomeAssistant,
) -> None:
    """Test significant states when significant_states_only is True."""
    now = dt_util.utcnow()
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "on", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "off", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "off", attributes={"any": "changed"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "off", attributes={"any": "again"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "on", attributes={"any": "attr"})
    await async_wait_recording_done(hass)

    hist = history.get_significant_states(
        hass,
        now,
        minimal_response=True,
        significant_changes_only=False,
        entity_ids=["sensor.test"],
    )
    assert len(hist["sensor.test"]) == 3


def record_states(
    hass: HomeAssistant,
) -> tuple[datetime, datetime, dict[str, list[State]]]:
    """Record some test states.

    We inject a bunch of state updates from media player, zone and
    thermostat.
    """
    mp = "media_player.test"
    mp2 = "media_player.test2"
    mp3 = "media_player.test3"
    therm = "thermostat.test"
    therm2 = "thermostat.test2"
    therm3 = "thermostat.test3"
    zone = "zone.home"
    script_c = "script.can_cancel_this_one"

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.async_set(entity_id, state, **kwargs)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(seconds=1)
    two = one + timedelta(seconds=1)
    three = two + timedelta(seconds=1)
    four = three + timedelta(seconds=1)

    states = {therm: [], therm2: [], therm3: [], mp: [], mp2: [], mp3: [], script_c: []}
    with freeze_time(one) as freezer:
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp2].append(
            set_state(mp2, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )
        states[mp3].append(
            set_state(mp3, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[therm].append(
            set_state(therm, 20, attributes={"current_temperature": 19.5})
        )
        # This state will be updated
        set_state(therm3, 20, attributes={"current_temperature": 19.5})

        freezer.move_to(one + timedelta(microseconds=1))
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )

        freezer.move_to(two)
        # This state will be skipped only different in time
        set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt3)})
        # This state will be skipped because domain is excluded
        set_state(zone, "zoning")
        states[script_c].append(
            set_state(script_c, "off", attributes={"can_cancel": True})
        )
        states[therm].append(
            set_state(therm, 21, attributes={"current_temperature": 19.8})
        )
        states[therm2].append(
            set_state(therm2, 20, attributes={"current_temperature": 19})
        )
        # This state will be updated
        set_state(therm3, 20, attributes={"current_temperature": 19.5})

        freezer.move_to(three)
        states[mp].append(
            set_state(mp, "Netflix", attributes={"media_title": str(sentinel.mt4)})
        )
        states[mp3].append(
            set_state(mp3, "Netflix", attributes={"media_title": str(sentinel.mt3)})
        )
        # Attributes changed even though state is the same
        states[therm].append(
            set_state(therm, 21, attributes={"current_temperature": 20})
        )
        states[therm3].append(
            set_state(therm3, 20, attributes={"current_temperature": 19.5})
        )

    return zero, four, states


async def test_get_full_significant_states_handles_empty_last_changed(
    hass: HomeAssistant,
) -> None:
    """Test getting states when last_changed is null."""
    now = dt_util.utcnow()
    hass.states.async_set("sensor.one", "on", {"attr": "original"})
    state0 = hass.states.get("sensor.one")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.one", "on", {"attr": "new"})
    state1 = hass.states.get("sensor.one")

    assert state0.last_changed == state1.last_changed
    assert state0.last_updated != state1.last_updated
    await async_wait_recording_done(hass)

    def _get_entries():
        with session_scope(hass=hass, read_only=True) as session:
            return history.get_full_significant_states_with_session(
                hass,
                session,
                now,
                dt_util.utcnow(),
                entity_ids=["sensor.one"],
                significant_changes_only=False,
            )

    states = await recorder.get_instance(hass).async_add_executor_job(_get_entries)
    sensor_one_states: list[State] = states["sensor.one"]
    assert_states_equal_without_context(sensor_one_states[0], state0)
    assert_states_equal_without_context(sensor_one_states[1], state1)
    assert sensor_one_states[0].last_changed == sensor_one_states[1].last_changed
    assert sensor_one_states[0].last_updated != sensor_one_states[1].last_updated

    def _fetch_native_states() -> list[State]:
        with session_scope(hass=hass, read_only=True) as session:
            native_states = []
            db_state_attributes = {
                state_attributes.attributes_id: state_attributes
                for state_attributes in session.query(StateAttributes)
            }
            metadata_id_to_entity_id = {
                states_meta.metadata_id: states_meta
                for states_meta in session.query(StatesMeta)
            }
            for db_state in session.query(States):
                db_state.entity_id = metadata_id_to_entity_id[
                    db_state.metadata_id
                ].entity_id
                state = db_state.to_native()
                state.attributes = db_state_attributes[
                    db_state.attributes_id
                ].to_native()
                native_states.append(state)
            return native_states

    native_sensor_one_states = await recorder.get_instance(hass).async_add_executor_job(
        _fetch_native_states
    )
    assert_states_equal_without_context(native_sensor_one_states[0], state0)
    assert_states_equal_without_context(native_sensor_one_states[1], state1)
    assert (
        native_sensor_one_states[0].last_changed
        == native_sensor_one_states[1].last_changed
    )
    assert (
        native_sensor_one_states[0].last_updated
        != native_sensor_one_states[1].last_updated
    )

    def _fetch_db_states() -> list[States]:
        with session_scope(hass=hass, read_only=True) as session:
            states = list(session.query(States))
            session.expunge_all()
            return states

    db_sensor_one_states = await recorder.get_instance(hass).async_add_executor_job(
        _fetch_db_states
    )
    assert db_sensor_one_states[0].last_changed is None
    assert db_sensor_one_states[0].last_changed_ts is None

    assert (
        process_timestamp(
            dt_util.utc_from_timestamp(db_sensor_one_states[1].last_changed_ts)
        )
        == state0.last_changed
    )
    assert db_sensor_one_states[0].last_updated_ts is not None
    assert db_sensor_one_states[1].last_updated_ts is not None
    assert (
        db_sensor_one_states[0].last_updated_ts
        != db_sensor_one_states[1].last_updated_ts
    )


async def test_state_changes_during_period_multiple_entities_single_test(
    hass: HomeAssistant,
) -> None:
    """Test state change during period with multiple entities in the same test.

    This test ensures the sqlalchemy query cache does not
    generate incorrect results.
    """
    start = dt_util.utcnow()
    test_entites = {f"sensor.{i}": str(i) for i in range(30)}
    for entity_id, value in test_entites.items():
        hass.states.async_set(entity_id, value)
    await async_wait_recording_done(hass)

    end = dt_util.utcnow()

    for entity_id, value in test_entites.items():
        hist = history.state_changes_during_period(hass, start, end, entity_id)
        assert len(hist) == 1
        assert hist[entity_id][0].state == value


@pytest.mark.freeze_time("2039-01-19 03:14:07.555555-00:00")
async def test_get_full_significant_states_past_year_2038(
    hass: HomeAssistant,
) -> None:
    """Test we can store times past year 2038."""
    past_2038_time = dt_util.parse_datetime("2039-01-19 03:14:07.555555-00:00")
    hass.states.async_set("sensor.one", "on", {"attr": "original"})
    state0 = hass.states.get("sensor.one")
    await hass.async_block_till_done()

    hass.states.async_set("sensor.one", "on", {"attr": "new"})
    state1 = hass.states.get("sensor.one")

    await async_wait_recording_done(hass)

    def _get_entries():
        with session_scope(hass=hass, read_only=True) as session:
            return history.get_full_significant_states_with_session(
                hass,
                session,
                past_2038_time - timedelta(days=365),
                past_2038_time + timedelta(days=365),
                entity_ids=["sensor.one"],
                significant_changes_only=False,
            )

    states = await recorder.get_instance(hass).async_add_executor_job(_get_entries)
    sensor_one_states: list[State] = states["sensor.one"]
    assert_states_equal_without_context(sensor_one_states[0], state0)
    assert_states_equal_without_context(sensor_one_states[1], state1)
    assert sensor_one_states[0].last_changed == past_2038_time
    assert sensor_one_states[0].last_updated == past_2038_time


async def test_get_significant_states_without_entity_ids_raises(
    hass: HomeAssistant,
) -> None:
    """Test at least one entity id is required for get_significant_states."""
    now = dt_util.utcnow()
    with pytest.raises(ValueError, match="entity_ids must be provided"):
        history.get_significant_states(hass, now, None)


async def test_state_changes_during_period_without_entity_ids_raises(
    hass: HomeAssistant,
) -> None:
    """Test at least one entity id is required for state_changes_during_period."""
    now = dt_util.utcnow()
    with pytest.raises(ValueError, match="entity_id must be provided"):
        history.state_changes_during_period(hass, now, None)


async def test_get_significant_states_with_filters_raises(
    hass: HomeAssistant,
) -> None:
    """Test passing filters is no longer supported."""
    now = dt_util.utcnow()
    with pytest.raises(NotImplementedError, match="Filters are no longer supported"):
        history.get_significant_states(
            hass, now, None, ["media_player.test"], Filters()
        )


async def test_get_significant_states_with_non_existent_entity_ids_returns_empty(
    hass: HomeAssistant,
) -> None:
    """Test get_significant_states returns an empty dict when entities not in the db."""
    now = dt_util.utcnow()
    assert history.get_significant_states(hass, now, None, ["nonexistent.entity"]) == {}


async def test_state_changes_during_period_with_non_existent_entity_ids_returns_empty(
    hass: HomeAssistant,
) -> None:
    """Test state_changes_during_period returns an empty dict when entities not in the db."""
    now = dt_util.utcnow()
    assert (
        history.state_changes_during_period(hass, now, None, "nonexistent.entity") == {}
    )


async def test_get_last_state_changes_with_non_existent_entity_ids_returns_empty(
    hass: HomeAssistant,
) -> None:
    """Test get_last_state_changes returns an empty dict when entities not in the db."""
    assert history.get_last_state_changes(hass, 1, "nonexistent.entity") == {}
