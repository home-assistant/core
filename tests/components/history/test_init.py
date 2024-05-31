"""The tests the History component."""

from datetime import timedelta
from http import HTTPStatus
import json
from unittest.mock import sentinel

from freezegun import freeze_time
import pytest

from homeassistant.components import history
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    assert_multiple_states_equal_without_context,
    assert_multiple_states_equal_without_context_and_last_changed,
    assert_states_equal_without_context,
    async_wait_recording_done,
)
from tests.typing import ClientSessionGenerator


def listeners_without_writes(listeners: dict[str, int]) -> dict[str, int]:
    """Return listeners without final write listeners since we are not testing for these."""
    return {
        key: value
        for key, value in listeners.items()
        if key != EVENT_HOMEASSISTANT_FINAL_WRITE
    }


@pytest.mark.usefixtures("hass_history")
async def test_setup() -> None:
    """Test setup method of history."""
    # Verification occurs in the fixture


async def test_get_significant_states(hass: HomeAssistant, hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = await async_record_states(hass)
    hist = get_significant_states(hass, zero, four, entity_ids=list(states))
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


async def test_get_significant_states_minimal_response(
    hass: HomeAssistant, hass_history
) -> None:
    """Test that only significant states are returned.

    When minimal responses is set only the first and
    last states return a complete state.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = await async_record_states(hass)
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


async def test_get_significant_states_with_initial(
    hass: HomeAssistant, hass_history
) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = await async_record_states(hass)
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

    hist = get_significant_states(
        hass, one_and_half, four, include_start_time_state=True, entity_ids=list(states)
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


async def test_get_significant_states_without_initial(
    hass: HomeAssistant, hass_history
) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    zero, four, states = await async_record_states(hass)
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

    hist = get_significant_states(
        hass,
        one_and_half,
        four,
        include_start_time_state=False,
        entity_ids=list(states),
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


async def test_get_significant_states_entity_id(
    hass: HomeAssistant, hass_history
) -> None:
    """Test that only significant states are returned for one entity."""
    zero, four, states = await async_record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    hist = get_significant_states(hass, zero, four, ["media_player.test"])
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


async def test_get_significant_states_multiple_entity_ids(
    hass: HomeAssistant, hass_history
) -> None:
    """Test that only significant states are returned for one entity."""
    zero, four, states = await async_record_states(hass)
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


async def test_get_significant_states_are_ordered(
    hass: HomeAssistant, hass_history
) -> None:
    """Test order of results from get_significant_states.

    When entity ids are given, the results should be returned with the data
    in the same order.
    """
    zero, four, _states = await async_record_states(hass)
    entity_ids = ["media_player.test", "media_player.test2"]
    hist = get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids
    entity_ids = ["media_player.test2", "media_player.test"]
    hist = get_significant_states(hass, zero, four, entity_ids)
    assert list(hist.keys()) == entity_ids


async def test_get_significant_states_only(hass: HomeAssistant, hass_history) -> None:
    """Test significant states when significant_states_only is set."""
    entity_id = "sensor.test"

    async def set_state(state, **kwargs):
        """Set the state."""
        hass.states.async_set(entity_id, state, **kwargs)
        await async_wait_recording_done(hass)
        return hass.states.get(entity_id)

    start = dt_util.utcnow() - timedelta(minutes=4)
    points = [start + timedelta(minutes=i) for i in range(1, 4)]

    states = []
    with freeze_time(start) as freezer:
        await set_state("123", attributes={"attribute": 10.64})

        freezer.move_to(points[0])
        # Attributes are different, state not
        states.append(await set_state("123", attributes={"attribute": 21.42}))

        freezer.move_to(points[1])
        # state is different, attributes not
        states.append(await set_state("32", attributes={"attribute": 21.42}))

        freezer.move_to(points[2])
        # everything is different
        states.append(await set_state("412", attributes={"attribute": 54.23}))

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


async def check_significant_states(hass, zero, four, states, config):
    """Check if significant states are retrieved."""
    hist = get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


async def async_record_states(hass):
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

    async def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.async_set(entity_id, state, **kwargs)
        await async_wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(seconds=1)
    two = one + timedelta(seconds=1)
    three = two + timedelta(seconds=1)
    four = three + timedelta(seconds=1)

    states = {therm: [], therm2: [], mp: [], mp2: [], mp3: [], script_c: []}
    with freeze_time(one) as freezer:
        states[mp].append(
            await set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp2].append(
            await set_state(
                mp2, "YouTube", attributes={"media_title": str(sentinel.mt2)}
            )
        )
        states[mp3].append(
            await set_state(mp3, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[therm].append(
            await set_state(therm, 20, attributes={"current_temperature": 19.5})
        )

        freezer.move_to(one + timedelta(microseconds=1))
        states[mp].append(
            await set_state(
                mp, "YouTube", attributes={"media_title": str(sentinel.mt2)}
            )
        )

        freezer.move_to(two)
        # This state will be skipped only different in time
        await set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt3)})
        # This state will be skipped because domain is excluded
        await set_state(zone, "zoning")
        states[script_c].append(
            await set_state(script_c, "off", attributes={"can_cancel": True})
        )
        states[therm].append(
            await set_state(therm, 21, attributes={"current_temperature": 19.8})
        )
        states[therm2].append(
            await set_state(therm2, 20, attributes={"current_temperature": 19})
        )

        freezer.move_to(three)
        states[mp].append(
            await set_state(
                mp, "Netflix", attributes={"media_title": str(sentinel.mt4)}
            )
        )
        states[mp3].append(
            await set_state(
                mp3, "Netflix", attributes={"media_title": str(sentinel.mt3)}
            )
        )
        # Attributes changed even though state is the same
        states[therm].append(
            await set_state(therm, 21, attributes={"current_temperature": 20})
        )

    return zero, four, states


async def test_fetch_period_api(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history."""
    await async_setup_component(hass, "history", {})
    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}?filter_entity_id=sensor.power"
    )
    assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_use_include_order(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the fetch period view for history with include order."""
    await async_setup_component(
        hass, "history", {history.DOMAIN: {history.CONF_ORDER: True}}
    )
    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}?filter_entity_id=sensor.power"
    )
    assert response.status == HTTPStatus.OK

    assert "The 'use_include_order' option is deprecated" in caplog.text


async def test_fetch_period_api_with_minimal_response(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with minimal_response."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "history", {})

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
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with no timestamp."""
    await async_setup_component(hass, "history", {})
    client = await hass_client()
    response = await client.get("/api/history/period?filter_entity_id=sensor.power")
    assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_include_order(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
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
    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}",
        params={"filter_entity_id": "non.existing,something.else"},
    )
    assert response.status == HTTPStatus.OK

    assert "The 'use_include_order' option is deprecated" in caplog.text
    assert "The 'include' option is deprecated" in caplog.text


async def test_entity_ids_limit_via_api(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test limiting history to entity_ids."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
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
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test limiting history to entity_ids with skip_initial_state."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
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


async def test_fetch_period_api_before_history_started(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history for the far past."""
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_wait_recording_done(hass)
    far_past = dt_util.utcnow() - timedelta(days=365)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{far_past.isoformat()}?filter_entity_id=light.kitchen",
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert response_json == []


async def test_fetch_period_api_far_future(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history for the far future."""
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_wait_recording_done(hass)
    far_future = dt_util.utcnow() + timedelta(days=365)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{far_future.isoformat()}?filter_entity_id=light.kitchen",
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert response_json == []


async def test_fetch_period_api_with_invalid_datetime(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with an invalid date time."""
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_wait_recording_done(hass)
    client = await hass_client()
    response = await client.get(
        "/api/history/period/INVALID?filter_entity_id=light.kitchen",
    )
    assert response.status == HTTPStatus.BAD_REQUEST
    response_json = await response.json()
    assert response_json == {"message": "Invalid datetime"}


async def test_fetch_period_api_invalid_end_time(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with an invalid end time."""
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_wait_recording_done(hass)
    far_past = dt_util.utcnow() - timedelta(days=365)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{far_past.isoformat()}",
        params={"filter_entity_id": "light.kitchen", "end_time": "INVALID"},
    )
    assert response.status == HTTPStatus.BAD_REQUEST
    response_json = await response.json()
    assert response_json == {"message": "Invalid end_time"}


async def test_entity_ids_limit_via_api_with_end_time(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test limiting history to entity_ids with end_time."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
    start = dt_util.utcnow()
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.cow", "on")
    hass.states.async_set("light.nomatch", "on")

    await async_wait_recording_done(hass)

    end_time = start + timedelta(minutes=1)
    future_second = dt_util.utcnow() + timedelta(seconds=1)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{future_second.isoformat()}",
        params={
            "filter_entity_id": "light.kitchen,light.cow",
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 0

    when = start - timedelta(minutes=1)
    response = await client.get(
        f"/api/history/period/{when.isoformat()}",
        params={
            "filter_entity_id": "light.kitchen,light.cow",
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0][0]["entity_id"] == "light.kitchen"
    assert response_json[1][0]["entity_id"] == "light.cow"


async def test_fetch_period_api_with_no_entity_ids(
    hass: HomeAssistant, recorder_mock: Recorder, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with minimal_response."""
    await async_setup_component(hass, "history", {})
    await async_wait_recording_done(hass)

    yesterday = dt_util.utcnow() - timedelta(days=1)

    client = await hass_client()
    response = await client.get(f"/api/history/period/{yesterday.isoformat()}")
    assert response.status == HTTPStatus.BAD_REQUEST
    response_json = await response.json()
    assert response_json == {"message": "filter_entity_id is missing"}


@pytest.mark.parametrize(
    ("filter_entity_id", "status_code", "response_contains1", "response_contains2"),
    [
        ("light.kitchen,light.cow", HTTPStatus.OK, "light.kitchen", "light.cow"),
        (
            "light.kitchen,light.cow&",
            HTTPStatus.BAD_REQUEST,
            "message",
            "Invalid filter_entity_id",
        ),
        (
            "light.kitchen,li-ght.cow",
            HTTPStatus.BAD_REQUEST,
            "message",
            "Invalid filter_entity_id",
        ),
        (
            "light.kit!chen",
            HTTPStatus.BAD_REQUEST,
            "message",
            "Invalid filter_entity_id",
        ),
        (
            "lig+ht.kitchen,light.cow",
            HTTPStatus.BAD_REQUEST,
            "message",
            "Invalid filter_entity_id",
        ),
        (
            "light.kitchenlight.cow",
            HTTPStatus.BAD_REQUEST,
            "message",
            "Invalid filter_entity_id",
        ),
        ("cow", HTTPStatus.BAD_REQUEST, "message", "Invalid filter_entity_id"),
    ],
)
async def test_history_with_invalid_entity_ids(
    hass: HomeAssistant,
    recorder_mock: Recorder,
    hass_client: ClientSessionGenerator,
    filter_entity_id,
    status_code,
    response_contains1,
    response_contains2,
) -> None:
    """Test sending valid and invalid entity_ids to the API."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.cow", "on")

    await async_wait_recording_done(hass)
    now = dt_util.utcnow().isoformat()
    client = await hass_client()

    response = await client.get(
        f"/api/history/period/{now}",
        params={"filter_entity_id": filter_entity_id},
    )
    assert response.status == status_code
    response_json = await response.json()
    assert response_contains1 in str(response_json)
    assert response_contains2 in str(response_json)
