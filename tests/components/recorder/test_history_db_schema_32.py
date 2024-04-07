"""The tests the History component."""

from __future__ import annotations

from collections.abc import Callable
from copy import copy
from datetime import datetime, timedelta
import json
from unittest.mock import patch, sentinel

from freezegun import freeze_time
import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import history
from homeassistant.components.recorder.filters import Filters
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.json import JSONEncoder
import homeassistant.util.dt as dt_util

from .common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    assert_multiple_states_equal_without_context,
    assert_multiple_states_equal_without_context_and_last_changed,
    assert_states_equal_without_context,
    old_db_schema,
    wait_recording_done,
)


@pytest.fixture(autouse=True)
def db_schema_32():
    """Fixture to initialize the db with the old schema 32."""
    with old_db_schema("32"):
        yield


def test_get_full_significant_states_with_session_entity_no_matches(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test getting states at a specific point in time for entities that never have been recorded."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    time_before_recorder_ran = now - timedelta(days=1000)
    instance = recorder.get_instance(hass)
    with (
        session_scope(hass=hass) as session,
        patch.object(instance.states_meta_manager, "active", False),
    ):
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


def test_significant_states_with_session_entity_minimal_response_no_matches(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test getting states at a specific point in time for entities that never have been recorded."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    time_before_recorder_ran = now - timedelta(days=1000)
    instance = recorder.get_instance(hass)
    with (
        session_scope(hass=hass) as session,
        patch.object(instance.states_meta_manager, "active", False),
    ):
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


@pytest.mark.parametrize(
    ("attributes", "no_attributes", "limit"),
    [
        ({"attr": True}, False, 5000),
        ({}, True, 5000),
        ({"attr": True}, False, 3),
        ({}, True, 3),
    ],
)
def test_state_changes_during_period(
    hass_recorder: Callable[..., HomeAssistant], attributes, no_attributes, limit
) -> None:
    """Test state change during period."""
    hass = hass_recorder()
    entity_id = "media_player.test"
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):

        def set_state(state):
            """Set the state."""
            hass.states.set(entity_id, state, attributes)
            wait_recording_done(hass)
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

        hist = history.state_changes_during_period(
            hass, start, end, entity_id, no_attributes, limit=limit
        )

        assert_multiple_states_equal_without_context(states[:limit], hist[entity_id])


def test_state_changes_during_period_descending(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test state change during period descending."""
    hass = hass_recorder()
    entity_id = "media_player.test"
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):

        def set_state(state):
            """Set the state."""
            hass.states.set(entity_id, state, {"any": 1})
            wait_recording_done(hass)
            return hass.states.get(entity_id)

        start = dt_util.utcnow()
        point = start + timedelta(seconds=1)
        point2 = start + timedelta(seconds=1, microseconds=2)
        point3 = start + timedelta(seconds=1, microseconds=3)
        point4 = start + timedelta(seconds=1, microseconds=4)
        end = point + timedelta(seconds=1)

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


def test_get_last_state_changes(hass_recorder: Callable[..., HomeAssistant]) -> None:
    """Test number of state changes."""
    hass = hass_recorder()
    entity_id = "sensor.test"
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):

        def set_state(state):
            """Set the state."""
            hass.states.set(entity_id, state)
            wait_recording_done(hass)
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

        hist = history.get_last_state_changes(hass, 2, entity_id)

        assert_multiple_states_equal_without_context(states, hist[entity_id])


def test_ensure_state_can_be_copied(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Ensure a state can pass though copy().

    The filter integration uses copy() on states
    from history.
    """
    hass = hass_recorder()
    entity_id = "sensor.test"
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):

        def set_state(state):
            """Set the state."""
            hass.states.set(entity_id, state)
            wait_recording_done(hass)
            return hass.states.get(entity_id)

        start = dt_util.utcnow() - timedelta(minutes=2)
        point = start + timedelta(minutes=1)

        with freeze_time(start) as freezer:
            set_state("1")

            freezer.move_to(point)
            set_state("2")

        hist = history.get_last_state_changes(hass, 2, entity_id)

        assert_states_equal_without_context(
            copy(hist[entity_id][0]), hist[entity_id][0]
        )
        assert_states_equal_without_context(
            copy(hist[entity_id][1]), hist[entity_id][1]
        )


def test_get_significant_states(hass_recorder: Callable[..., HomeAssistant]) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, states = record_states(hass)
        hist = history.get_significant_states(hass, zero, four, entity_ids=list(states))
        assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_minimal_response(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test that only significant states are returned.

    When minimal responses is set only the first and
    last states return a complete state.
    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, states = record_states(hass)
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


@pytest.mark.parametrize("time_zone", ["Europe/Berlin", "US/Hawaii", "UTC"])
def test_get_significant_states_with_initial(
    time_zone, hass_recorder: Callable[..., HomeAssistant]
) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    hass.config.set_time_zone(time_zone)
    zero, four, states = record_states(hass)
    one = zero + timedelta(seconds=1)
    one_and_half = zero + timedelta(seconds=1.5)
    for entity_id in states:
        if entity_id == "media_player.test":
            states[entity_id] = states[entity_id][1:]
        for state in states[entity_id]:
            if state.last_changed == one:
                state.last_changed = one_and_half

    hist = history.get_significant_states(
        hass, one_and_half, four, include_start_time_state=True, entity_ids=list(states)
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_without_initial(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, states = record_states(hass)
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

        hist = history.get_significant_states(
            hass,
            one_and_half,
            four,
            include_start_time_state=False,
            entity_ids=list(states),
        )
        assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_entity_id(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test that only significant states are returned for one entity."""
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, states = record_states(hass)
        del states["media_player.test2"]
        del states["media_player.test3"]
        del states["thermostat.test"]
        del states["thermostat.test2"]
        del states["script.can_cancel_this_one"]

        hist = history.get_significant_states(hass, zero, four, ["media_player.test"])
        assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_multiple_entity_ids(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test that only significant states are returned for one entity."""
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, states = record_states(hass)
        del states["media_player.test2"]
        del states["media_player.test3"]
        del states["thermostat.test2"]
        del states["script.can_cancel_this_one"]

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


def test_get_significant_states_are_ordered(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test order of results from get_significant_states.

    When entity ids are given, the results should be returned with the data
    in the same order.
    """
    hass = hass_recorder()

    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, _states = record_states(hass)
        entity_ids = ["media_player.test", "media_player.test2"]
        hist = history.get_significant_states(hass, zero, four, entity_ids)
        assert list(hist.keys()) == entity_ids
        entity_ids = ["media_player.test2", "media_player.test"]
        hist = history.get_significant_states(hass, zero, four, entity_ids)
        assert list(hist.keys()) == entity_ids


def test_get_significant_states_only(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test significant states when significant_states_only is set."""
    hass = hass_recorder()
    entity_id = "sensor.test"
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):

        def set_state(state, **kwargs):
            """Set the state."""
            hass.states.set(entity_id, state, **kwargs)
            wait_recording_done(hass)
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


def record_states(hass) -> tuple[datetime, datetime, dict[str, list[State]]]:
    """Record some test states.

    We inject a bunch of state updates from media player, zone and
    thermostat.
    """
    mp = "media_player.test"
    mp2 = "media_player.test2"
    mp3 = "media_player.test3"
    therm = "thermostat.test"
    therm2 = "thermostat.test2"
    zone = "zone.home"
    script_c = "script.can_cancel_this_one"

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(seconds=1)
    two = one + timedelta(seconds=1)
    three = two + timedelta(seconds=1)
    four = three + timedelta(seconds=1)

    states = {therm: [], therm2: [], mp: [], mp2: [], mp3: [], script_c: []}
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

    return zero, four, states


def test_state_changes_during_period_multiple_entities_single_test(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test state change during period with multiple entities in the same test.

    This test ensures the sqlalchemy query cache does not
    generate incorrect results.
    """
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        start = dt_util.utcnow()
        test_entites = {f"sensor.{i}": str(i) for i in range(30)}
        for entity_id, value in test_entites.items():
            hass.states.set(entity_id, value)

        wait_recording_done(hass)
        end = dt_util.utcnow()

        for entity_id, value in test_entites.items():
            hist = history.state_changes_during_period(hass, start, end, entity_id)
            assert len(hist) == 1
            assert hist[entity_id][0].state == value


def test_get_significant_states_without_entity_ids_raises(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test at least one entity id is required for get_significant_states."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    with pytest.raises(ValueError, match="entity_ids must be provided"):
        history.get_significant_states(hass, now, None)


def test_state_changes_during_period_without_entity_ids_raises(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test at least one entity id is required for state_changes_during_period."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    with pytest.raises(ValueError, match="entity_id must be provided"):
        history.state_changes_during_period(hass, now, None)


def test_get_significant_states_with_filters_raises(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test passing filters is no longer supported."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    with pytest.raises(NotImplementedError, match="Filters are no longer supported"):
        history.get_significant_states(
            hass, now, None, ["media_player.test"], Filters()
        )


def test_get_significant_states_with_non_existent_entity_ids_returns_empty(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test get_significant_states returns an empty dict when entities not in the db."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    assert history.get_significant_states(hass, now, None, ["nonexistent.entity"]) == {}


def test_state_changes_during_period_with_non_existent_entity_ids_returns_empty(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test state_changes_during_period returns an empty dict when entities not in the db."""
    hass = hass_recorder()
    now = dt_util.utcnow()
    assert (
        history.state_changes_during_period(hass, now, None, "nonexistent.entity") == {}
    )


def test_get_last_state_changes_with_non_existent_entity_ids_returns_empty(
    hass_recorder: Callable[..., HomeAssistant],
) -> None:
    """Test get_last_state_changes returns an empty dict when entities not in the db."""
    hass = hass_recorder()
    assert history.get_last_state_changes(hass, 1, "nonexistent.entity") == {}
