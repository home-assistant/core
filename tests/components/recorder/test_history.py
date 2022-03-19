"""The tests the History component."""
# pylint: disable=protected-access,invalid-name
from copy import copy
from datetime import timedelta
import json
from unittest.mock import patch, sentinel

from homeassistant.components.recorder import history
from homeassistant.components.recorder.models import process_timestamp
import homeassistant.core as ha
from homeassistant.helpers.json import JSONEncoder
import homeassistant.util.dt as dt_util

from tests.common import mock_state_change_event
from tests.components.recorder.common import wait_recording_done


def test_get_states(hass_recorder):
    """Test getting states at a specific point in time."""
    hass = hass_recorder()
    states = []

    now = dt_util.utcnow()
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=now):
        for i in range(5):
            state = ha.State(
                f"test.point_in_time_{i % 5}",
                f"State {i}",
                {"attribute_test": i},
            )

            mock_state_change_event(hass, state)

            states.append(state)

        wait_recording_done(hass)

    future = now + timedelta(seconds=1)
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=future):
        for i in range(5):
            state = ha.State(
                f"test.point_in_time_{i % 5}",
                f"State {i}",
                {"attribute_test": i},
            )

            mock_state_change_event(hass, state)

        wait_recording_done(hass)

    # Get states returns everything before POINT for all entities
    for state1, state2 in zip(
        states,
        sorted(history.get_states(hass, future), key=lambda state: state.entity_id),
    ):
        assert state1 == state2

    # Get states returns everything before POINT for tested entities
    entities = [f"test.point_in_time_{i % 5}" for i in range(5)]
    for state1, state2 in zip(
        states,
        sorted(
            history.get_states(hass, future, entities),
            key=lambda state: state.entity_id,
        ),
    ):
        assert state1 == state2

    # Test get_state here because we have a DB setup
    assert states[0] == history.get_state(hass, future, states[0].entity_id)

    time_before_recorder_ran = now - timedelta(days=1000)
    assert history.get_states(hass, time_before_recorder_ran) == []

    assert history.get_state(hass, time_before_recorder_ran, "demo.id") is None


def test_state_changes_during_period(hass_recorder):
    """Test state change during period."""
    hass = hass_recorder()
    entity_id = "media_player.test"

    def set_state(state):
        """Set the state."""
        hass.states.set(entity_id, state)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    start = dt_util.utcnow()
    point = start + timedelta(seconds=1)
    end = point + timedelta(seconds=1)

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=start):
        set_state("idle")
        set_state("YouTube")

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=point):
        states = [
            set_state("idle"),
            set_state("Netflix"),
            set_state("Plex"),
            set_state("YouTube"),
        ]

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=end):
        set_state("Netflix")
        set_state("Plex")

    hist = history.state_changes_during_period(hass, start, end, entity_id)

    assert states == hist[entity_id]


def test_get_last_state_changes(hass_recorder):
    """Test number of state changes."""
    hass = hass_recorder()
    entity_id = "sensor.test"

    def set_state(state):
        """Set the state."""
        hass.states.set(entity_id, state)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=2)
    point = start + timedelta(minutes=1)
    point2 = point + timedelta(minutes=1)

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=start):
        set_state("1")

    states = []
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=point):
        states.append(set_state("2"))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=point2):
        states.append(set_state("3"))

    hist = history.get_last_state_changes(hass, 2, entity_id)

    assert states == hist[entity_id]


def test_ensure_state_can_be_copied(hass_recorder):
    """Ensure a state can pass though copy().

    The filter integration uses copy() on states
    from history.
    """
    hass = hass_recorder()
    entity_id = "sensor.test"

    def set_state(state):
        """Set the state."""
        hass.states.set(entity_id, state)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=2)
    point = start + timedelta(minutes=1)

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=start):
        set_state("1")

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=point):
        set_state("2")

    hist = history.get_last_state_changes(hass, 2, entity_id)

    assert copy(hist[entity_id][0]) == hist[entity_id][0]
    assert copy(hist[entity_id][1]) == hist[entity_id][1]


def test_get_significant_states(hass_recorder):
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    import pprint

    pprint.pprint([hist, states])
    assert states == hist


def test_get_significant_states_minimal_response(hass_recorder):
    """Test that only significant states are returned.

    When minimal responses is set only the first and
    last states return a complete state.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four, minimal_response=True)

    # The second media_player.test state is reduced
    # down to last_changed and state when minimal_response
    # is set.  We use JSONEncoder to make sure that are
    # pre-encoded last_changed is always the same as what
    # will happen with encoding a native state
    input_state = states["media_player.test"][1]
    orig_last_changed = json.dumps(
        process_timestamp(input_state.last_changed),
        cls=JSONEncoder,
    ).replace('"', "")
    orig_state = input_state.state
    states["media_player.test"][1] = {
        "last_changed": orig_last_changed,
        "state": orig_state,
    }

    assert states == hist


def test_get_significant_states_with_initial(hass_recorder):
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
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
        hass,
        one_and_half,
        four,
        include_start_time_state=True,
    )
    assert states == hist


def test_get_significant_states_without_initial(hass_recorder):
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_recorder()
    zero, four, states = record_states(hass)
    one = zero + timedelta(seconds=1)
    one_and_half = zero + timedelta(seconds=1.5)
    for entity_id in states:
        states[entity_id] = list(
            filter(lambda s: s.last_changed != one, states[entity_id])
        )
    del states["media_player.test2"]

    hist = history.get_significant_states(
        hass,
        one_and_half,
        four,
        include_start_time_state=False,
    )
    assert states == hist


def test_get_significant_states_entity_id(hass_recorder):
    """Test that only significant states are returned for one entity."""
    hass = hass_recorder()
    zero, four, states = record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    hist = history.get_significant_states(hass, zero, four, ["media_player.test"])
    assert states == hist


def test_get_significant_states_multiple_entity_ids(hass_recorder):
    """Test that only significant states are returned for one entity."""
    hass = hass_recorder()
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
    assert states == hist


def test_get_significant_states_are_ordered(hass_recorder):
    """Test order of results from get_significant_states.

    When entity ids are given, the results should be returned with the data
    in the same order.
    """
    hass = hass_recorder()
    zero, four, _states = record_states(hass)
    entity_ids = ["media_player.test", "media_player.test2"]
    hist = history.get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids
    entity_ids = ["media_player.test2", "media_player.test"]
    hist = history.get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids


def test_get_significant_states_only(hass_recorder):
    """Test significant states when significant_states_only is set."""
    hass = hass_recorder()
    entity_id = "sensor.test"

    def set_state(state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=4)
    points = []
    for i in range(1, 4):
        points.append(start + timedelta(minutes=i))

    states = []
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=start):
        set_state("123", attributes={"attribute": 10.64})

    with patch(
        "homeassistant.components.recorder.dt_util.utcnow", return_value=points[0]
    ):
        # Attributes are different, state not
        states.append(set_state("123", attributes={"attribute": 21.42}))

    with patch(
        "homeassistant.components.recorder.dt_util.utcnow", return_value=points[1]
    ):
        # state is different, attributes not
        states.append(set_state("32", attributes={"attribute": 21.42}))

    with patch(
        "homeassistant.components.recorder.dt_util.utcnow", return_value=points[2]
    ):
        # everything is different
        states.append(set_state("412", attributes={"attribute": 54.23}))

    hist = history.get_significant_states(hass, start, significant_changes_only=True)

    assert len(hist[entity_id]) == 2
    assert states[0] not in hist[entity_id]
    assert states[1] in hist[entity_id]
    assert states[2] in hist[entity_id]

    hist = history.get_significant_states(hass, start, significant_changes_only=False)

    assert len(hist[entity_id]) == 3
    assert states == hist[entity_id]


def record_states(hass):
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
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
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

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
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

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
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
