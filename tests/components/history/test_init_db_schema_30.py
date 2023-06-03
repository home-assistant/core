"""The tests the History component."""
from __future__ import annotations

# pylint: disable=invalid-name
from datetime import timedelta
from http import HTTPStatus
import json
from unittest.mock import patch, sentinel

from freezegun import freeze_time
import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    assert_multiple_states_equal_without_context,
    assert_multiple_states_equal_without_context_and_last_changed,
    assert_states_equal_without_context,
    async_recorder_block_till_done,
    async_wait_recording_done,
    old_db_schema,
    wait_recording_done,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
def db_schema_30():
    """Fixture to initialize the db with the old schema 30."""
    with old_db_schema("30"):
        yield


@pytest.fixture
def legacy_hass_history(hass_history):
    """Home Assistant fixture to use legacy history recording."""
    instance = recorder.get_instance(hass_history)
    with patch.object(instance.states_meta_manager, "active", False):
        yield hass_history


@pytest.mark.usefixtures("legacy_hass_history")
def test_setup() -> None:
    """Test setup method of history."""
    # Verification occurs in the fixture


def test_get_significant_states(legacy_hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = legacy_hass_history
    zero, four, states = record_states(hass)
    hist = get_significant_states(hass, zero, four, entity_ids=list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_minimal_response(legacy_hass_history) -> None:
    """Test that only significant states are returned.

    When minimal responses is set only the first and
    last states return a complete state.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = legacy_hass_history
    zero, four, states = record_states(hass)
    hist = get_significant_states(
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
            orig_last_changed = orig_last_changed = json.dumps(
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


def test_get_significant_states_with_initial(legacy_hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = legacy_hass_history
    zero, four, states = record_states(hass)
    one = zero + timedelta(seconds=1)
    one_with_microsecond = zero + timedelta(seconds=1, microseconds=1)
    one_and_half = zero + timedelta(seconds=1.5)
    for entity_id in states:
        if entity_id == "media_player.test":
            states[entity_id] = states[entity_id][1:]
        for state in states[entity_id]:
            if state.last_changed == one or state.last_changed == one_with_microsecond:
                state.last_changed = one_and_half
                state.last_updated = one_and_half

    hist = get_significant_states(
        hass,
        one_and_half,
        four,
        include_start_time_state=True,
        entity_ids=list(states),
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_without_initial(legacy_hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = legacy_hass_history
    zero, four, states = record_states(hass)
    one = zero + timedelta(seconds=1)
    one_with_microsecond = zero + timedelta(seconds=1, microseconds=1)
    one_and_half = zero + timedelta(seconds=1.5)
    for entity_id in states:
        states[entity_id] = list(
            filter(
                lambda s: s.last_changed != one
                and s.last_changed != one_with_microsecond,
                states[entity_id],
            )
        )
    del states["media_player.test2"]

    hist = get_significant_states(
        hass,
        one_and_half,
        four,
        include_start_time_state=False,
        entity_ids=list(states),
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_entity_id(hass_history) -> None:
    """Test that only significant states are returned for one entity."""
    hass = hass_history

    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        zero, four, states = record_states(hass)
        del states["media_player.test2"]
        del states["media_player.test3"]
        del states["thermostat.test"]
        del states["thermostat.test2"]
        del states["script.can_cancel_this_one"]

        hist = get_significant_states(hass, zero, four, ["media_player.test"])
        assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_multiple_entity_ids(legacy_hass_history) -> None:
    """Test that only significant states are returned for one entity."""
    hass = legacy_hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    hist = get_significant_states(
        hass,
        zero,
        four,
        ["media_player.test", "thermostat.test"],
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_are_ordered(legacy_hass_history) -> None:
    """Test order of results from get_significant_states.

    When entity ids are given, the results should be returned with the data
    in the same order.
    """
    hass = legacy_hass_history
    zero, four, _states = record_states(hass)
    entity_ids = ["media_player.test", "media_player.test2"]
    hist = get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids
    entity_ids = ["media_player.test2", "media_player.test"]
    hist = get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids


def test_get_significant_states_only(legacy_hass_history) -> None:
    """Test significant states when significant_states_only is set."""
    hass = legacy_hass_history
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

    hist = get_significant_states(
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

    hist = get_significant_states(
        hass,
        start,
        significant_changes_only=False,
        entity_ids=list({state.entity_id for state in states}),
    )

    assert len(hist[entity_id]) == 3
    assert_multiple_states_equal_without_context_and_last_changed(
        states, hist[entity_id]
    )


def check_significant_states(hass, zero, four, states, config):
    """Check if significant states are retrieved."""
    hist = get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


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


async def test_fetch_period_api(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history."""
    await async_setup_component(hass, "history", {})
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        client = await hass_client()
        response = await client.get(
            f"/api/history/period/{dt_util.utcnow().isoformat()}?filter_entity_id=sensor.power"
        )
        assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_minimal_response(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with minimal_response."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "history", {})
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        hass.states.async_set("sensor.power", 0, {"attr": "any"})
        await async_wait_recording_done(hass)
        hass.states.async_set("sensor.power", 50, {"attr": "any"})
        await async_wait_recording_done(hass)
        hass.states.async_set("sensor.power", 23, {"attr": "any"})
        last_changed = hass.states.get("sensor.power").last_changed
        await async_wait_recording_done(hass)
        hass.states.async_set("sensor.power", 23, {"attr": "any"})
        await async_wait_recording_done(hass)
        client = await hass_client()
        response = await client.get(
            f"/api/history/period/{now.isoformat()}?filter_entity_id=sensor.power&minimal_response&no_attributes"
        )
        assert response.status == HTTPStatus.OK
        response_json = await response.json()
        assert len(response_json[0]) == 3
        state_list = response_json[0]

        assert state_list[0]["entity_id"] == "sensor.power"
        assert state_list[0]["attributes"] == {}
        assert state_list[0]["state"] == "0"

        assert "attributes" not in state_list[1]
        assert "entity_id" not in state_list[1]
        assert state_list[1]["state"] == "50"

        assert "attributes" not in state_list[2]
        assert "entity_id" not in state_list[2]
        assert state_list[2]["state"] == "23"
        assert state_list[2]["last_changed"] == json.dumps(
            process_timestamp(last_changed),
            cls=JSONEncoder,
        ).replace('"', "")


async def test_fetch_period_api_with_no_timestamp(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with no timestamp."""
    await async_setup_component(hass, "history", {})
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        client = await hass_client()
        response = await client.get("/api/history/period?filter_entity_id=sensor.power")
        assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_include_order(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history."""
    await async_setup_component(
        hass,
        "history",
        {
            "history": {
                "use_include_order": True,
                "include": {"entities": ["light.kitchen"]},
            }
        },
    )
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        client = await hass_client()
        response = await client.get(
            f"/api/history/period/{dt_util.utcnow().isoformat()}",
            params={"filter_entity_id": "non.existing,something.else"},
        )
        assert response.status == HTTPStatus.OK


async def test_entity_ids_limit_via_api(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test limiting history to entity_ids."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        hass.states.async_set("light.kitchen", "on")
        hass.states.async_set("light.cow", "on")
        hass.states.async_set("light.nomatch", "on")

        await async_wait_recording_done(hass)

        client = await hass_client()
        response = await client.get(
            f"/api/history/period/{dt_util.utcnow().isoformat()}?filter_entity_id=light.kitchen,light.cow",
        )
        assert response.status == HTTPStatus.OK
        response_json = await response.json()
        assert len(response_json) == 2
        assert response_json[0][0]["entity_id"] == "light.kitchen"
        assert response_json[1][0]["entity_id"] == "light.cow"


async def test_entity_ids_limit_via_api_with_skip_initial_state(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test limiting history to entity_ids with skip_initial_state."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        hass.states.async_set("light.kitchen", "on")
        hass.states.async_set("light.cow", "on")
        hass.states.async_set("light.nomatch", "on")

        await async_wait_recording_done(hass)

        client = await hass_client()
        response = await client.get(
            f"/api/history/period/{dt_util.utcnow().isoformat()}?filter_entity_id=light.kitchen,light.cow&skip_initial_state",
        )
        assert response.status == HTTPStatus.OK
        response_json = await response.json()
        assert len(response_json) == 0

        when = dt_util.utcnow() - timedelta(minutes=1)
        response = await client.get(
            f"/api/history/period/{when.isoformat()}?filter_entity_id=light.kitchen,light.cow&skip_initial_state",
        )
        assert response.status == HTTPStatus.OK
        response_json = await response.json()
        assert len(response_json) == 2
        assert response_json[0][0]["entity_id"] == "light.kitchen"
        assert response_json[1][0]["entity_id"] == "light.cow"


async def test_history_during_period(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
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

        await async_wait_recording_done(hass)

        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "end_time": now.isoformat(),
                "entity_ids": ["sensor.test"],
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == {}

        await client.send_json(
            {
                "id": 2,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "entity_ids": ["sensor.test"],
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": True,
                "minimal_response": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 2

        sensor_test_history = response["result"]["sensor.test"]
        assert len(sensor_test_history) == 3

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {}
        assert isinstance(sensor_test_history[0]["lu"], float)
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)

        assert "a" not in sensor_test_history[1]
        assert sensor_test_history[1]["s"] == "off"
        assert isinstance(sensor_test_history[1]["lu"], float)
        assert (
            "lc" not in sensor_test_history[1]
        )  # skipped if the same a last_updated (lu)

        assert sensor_test_history[2]["s"] == "on"
        assert "a" not in sensor_test_history[2]

        await client.send_json(
            {
                "id": 3,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "entity_ids": ["sensor.test"],
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": False,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 3
        sensor_test_history = response["result"]["sensor.test"]

        assert len(sensor_test_history) == 5

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {"any": "attr"}
        assert isinstance(sensor_test_history[0]["lu"], float)
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)

        assert sensor_test_history[1]["s"] == "off"
        assert isinstance(sensor_test_history[1]["lu"], float)
        assert (
            "lc" not in sensor_test_history[1]
        )  # skipped if the same a last_updated (lu)
        assert sensor_test_history[1]["a"] == {"any": "attr"}

        assert sensor_test_history[4]["s"] == "on"
        assert sensor_test_history[4]["a"] == {"any": "attr"}

        await client.send_json(
            {
                "id": 4,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "entity_ids": ["sensor.test"],
                "include_start_time_state": True,
                "significant_changes_only": True,
                "no_attributes": False,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 4
        sensor_test_history = response["result"]["sensor.test"]

        assert len(sensor_test_history) == 3

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {"any": "attr"}
        assert isinstance(sensor_test_history[0]["lu"], float)
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)

        assert sensor_test_history[1]["s"] == "off"
        assert isinstance(sensor_test_history[1]["lu"], float)
        assert (
            "lc" not in sensor_test_history[1]
        )  # skipped if the same a last_updated (lu)
        assert sensor_test_history[1]["a"] == {"any": "attr"}

        assert sensor_test_history[2]["s"] == "on"
        assert sensor_test_history[2]["a"] == {"any": "attr"}


async def test_history_during_period_impossible_conditions(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period returns when condition cannot be true."""
    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
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

        await async_wait_recording_done(hass)

        after = dt_util.utcnow()

        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "history/history_during_period",
                "start_time": after.isoformat(),
                "end_time": after.isoformat(),
                "entity_ids": ["sensor.test"],
                "include_start_time_state": False,
                "significant_changes_only": False,
                "no_attributes": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 1
        assert response["result"] == {}

        future = dt_util.utcnow() + timedelta(hours=10)

        await client.send_json(
            {
                "id": 2,
                "type": "history/history_during_period",
                "start_time": future.isoformat(),
                "entity_ids": ["sensor.test"],
                "include_start_time_state": True,
                "significant_changes_only": True,
                "no_attributes": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 2
        assert response["result"] == {}


@pytest.mark.parametrize(
    "time_zone", ["UTC", "Europe/Berlin", "America/Chicago", "US/Hawaii"]
)
async def test_history_during_period_significant_domain(
    time_zone,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test history_during_period with climate domain."""
    hass.config.set_time_zone(time_zone)
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        hass.states.async_set("climate.test", "on", attributes={"temperature": "1"})
        await async_recorder_block_till_done(hass)
        hass.states.async_set("climate.test", "off", attributes={"temperature": "2"})
        await async_recorder_block_till_done(hass)
        hass.states.async_set("climate.test", "off", attributes={"temperature": "3"})
        await async_recorder_block_till_done(hass)
        hass.states.async_set("climate.test", "off", attributes={"temperature": "4"})
        await async_recorder_block_till_done(hass)
        hass.states.async_set("climate.test", "on", attributes={"temperature": "5"})
        await async_wait_recording_done(hass)

        await async_wait_recording_done(hass)

        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "end_time": now.isoformat(),
                "entity_ids": ["climate.test"],
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == {}

        await client.send_json(
            {
                "id": 2,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "entity_ids": ["climate.test"],
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": True,
                "minimal_response": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 2

        sensor_test_history = response["result"]["climate.test"]
        assert len(sensor_test_history) == 5

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {}
        assert isinstance(sensor_test_history[0]["lu"], float)
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)

        assert "a" in sensor_test_history[1]
        assert sensor_test_history[1]["s"] == "off"
        assert (
            "lc" not in sensor_test_history[1]
        )  # skipped if the same a last_updated (lu)

        assert sensor_test_history[4]["s"] == "on"
        assert sensor_test_history[4]["a"] == {}

        await client.send_json(
            {
                "id": 3,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "entity_ids": ["climate.test"],
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": False,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 3
        sensor_test_history = response["result"]["climate.test"]

        assert len(sensor_test_history) == 5

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {"temperature": "1"}
        assert isinstance(sensor_test_history[0]["lu"], float)
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)

        assert sensor_test_history[1]["s"] == "off"
        assert isinstance(sensor_test_history[1]["lu"], float)
        assert (
            "lc" not in sensor_test_history[1]
        )  # skipped if the same a last_updated (lu)
        assert sensor_test_history[1]["a"] == {"temperature": "2"}

        assert sensor_test_history[4]["s"] == "on"
        assert sensor_test_history[4]["a"] == {"temperature": "5"}

        await client.send_json(
            {
                "id": 4,
                "type": "history/history_during_period",
                "start_time": now.isoformat(),
                "entity_ids": ["climate.test"],
                "include_start_time_state": True,
                "significant_changes_only": True,
                "no_attributes": False,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 4
        sensor_test_history = response["result"]["climate.test"]

        assert len(sensor_test_history) == 5

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {"temperature": "1"}
        assert isinstance(sensor_test_history[0]["lu"], float)
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)

        assert sensor_test_history[1]["s"] == "off"
        assert isinstance(sensor_test_history[1]["lu"], float)
        assert (
            "lc" not in sensor_test_history[1]
        )  # skipped if the same a last_updated (lu)
        assert sensor_test_history[1]["a"] == {"temperature": "2"}

        assert sensor_test_history[2]["s"] == "off"
        assert sensor_test_history[2]["a"] == {"temperature": "3"}

        assert sensor_test_history[3]["s"] == "off"
        assert sensor_test_history[3]["a"] == {"temperature": "4"}

        assert sensor_test_history[4]["s"] == "on"
        assert sensor_test_history[4]["a"] == {"temperature": "5"}

        # Test we impute the state time state
        later = dt_util.utcnow()
        await client.send_json(
            {
                "id": 5,
                "type": "history/history_during_period",
                "start_time": later.isoformat(),
                "entity_ids": ["climate.test"],
                "include_start_time_state": True,
                "significant_changes_only": True,
                "no_attributes": False,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 5
        sensor_test_history = response["result"]["climate.test"]

        assert len(sensor_test_history) == 1

        assert sensor_test_history[0]["s"] == "on"
        assert sensor_test_history[0]["a"] == {"temperature": "5"}
        assert sensor_test_history[0]["lu"] == later.timestamp()
        assert (
            "lc" not in sensor_test_history[0]
        )  # skipped if the same a last_updated (lu)


async def test_history_during_period_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period bad state time."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "history/history_during_period",
                "entity_ids": ["sensor.pet"],
                "start_time": "cats",
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert response["error"]["code"] == "invalid_start_time"


async def test_history_during_period_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period bad end time."""
    now = dt_util.utcnow()

    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
    instance = recorder.get_instance(hass)
    with patch.object(instance.states_meta_manager, "active", False):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "history/history_during_period",
                "entity_ids": ["sensor.pet"],
                "start_time": now.isoformat(),
                "end_time": "dogs",
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert response["error"]["code"] == "invalid_end_time"
