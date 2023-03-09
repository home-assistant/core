"""The tests the History component."""
from __future__ import annotations

# pylint: disable=invalid-name
from datetime import timedelta
from http import HTTPStatus
import importlib
import json
import sys
from unittest.mock import patch, sentinel

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from homeassistant.components import history, recorder
from homeassistant.components.recorder import Recorder, core, statistics
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
import homeassistant.core as ha
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
    wait_recording_done,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE = "tests.components.recorder.db_schema_30"


def _create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]
    engine = create_engine(*args, **kwargs)
    old_db_schema.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            recorder.db_schema.StatisticsRuns(start=statistics.get_start_time())
        )
        session.add(
            recorder.db_schema.SchemaChanges(
                schema_version=old_db_schema.SCHEMA_VERSION
            )
        )
        session.commit()
    return engine


@pytest.fixture(autouse=True)
def db_schema_30():
    """Fixture to initialize the db with the old schema."""
    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]

    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch.object(core, "EventData", old_db_schema.EventData), patch.object(
        core, "States", old_db_schema.States
    ), patch.object(
        core, "Events", old_db_schema.Events
    ), patch.object(
        core, "StateAttributes", old_db_schema.StateAttributes
    ), patch(
        CREATE_ENGINE_TARGET, new=_create_engine_test
    ):
        yield


@pytest.mark.usefixtures("hass_history")
def test_setup() -> None:
    """Test setup method of history."""
    # Verification occurs in the fixture


def test_get_significant_states(hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    hist = get_significant_states(hass, zero, four, filters=history.Filters())
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_minimal_response(hass_history) -> None:
    """Test that only significant states are returned.

    When minimal responses is set only the first and
    last states return a complete state.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    hist = get_significant_states(
        hass, zero, four, filters=history.Filters(), minimal_response=True
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


def test_get_significant_states_with_initial(hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_history
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
        filters=history.Filters(),
        include_start_time_state=True,
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_without_initial(hass_history) -> None:
    """Test that only significant states are returned.

    We should get back every thermostat change that
    includes an attribute change, but only the state updates for
    media player (attribute changes are not significant and not returned).
    """
    hass = hass_history
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
        filters=history.Filters(),
        include_start_time_state=False,
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_entity_id(hass_history) -> None:
    """Test that only significant states are returned for one entity."""
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    hist = get_significant_states(
        hass, zero, four, ["media_player.test"], filters=history.Filters()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_multiple_entity_ids(hass_history) -> None:
    """Test that only significant states are returned for one entity."""
    hass = hass_history
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
        filters=history.Filters(),
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)


def test_get_significant_states_exclude_domain(hass_history) -> None:
    """Test if significant states are returned when excluding domains.

    We should get back every thermostat change that includes an attribute
    change, but no media player changes.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test"]
    del states["media_player.test2"]
    del states["media_player.test3"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {CONF_EXCLUDE: {CONF_DOMAINS: ["media_player"]}},
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_exclude_entity(hass_history) -> None:
    """Test if significant states are returned when excluding entities.

    We should get back every thermostat and script changes, but no media
    player changes.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {CONF_EXCLUDE: {CONF_ENTITIES: ["media_player.test"]}},
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_exclude(hass_history) -> None:
    """Test significant states when excluding entities and domains.

    We should not get back every thermostat and media player test changes.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test"]
    del states["thermostat.test"]
    del states["thermostat.test2"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["thermostat"],
                    CONF_ENTITIES: ["media_player.test"],
                }
            },
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_exclude_include_entity(hass_history) -> None:
    """Test significant states when excluding domains and include entities.

    We should not get back every thermostat change unless its specifically included
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["thermostat.test2"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {
                CONF_INCLUDE: {CONF_ENTITIES: ["media_player.test", "thermostat.test"]},
                CONF_EXCLUDE: {CONF_DOMAINS: ["thermostat"]},
            },
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_include_domain(hass_history) -> None:
    """Test if significant states are returned when including domains.

    We should get back every thermostat and script changes, but no media
    player changes.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test"]
    del states["media_player.test2"]
    del states["media_player.test3"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {CONF_INCLUDE: {CONF_DOMAINS: ["thermostat", "script"]}},
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_include_entity(hass_history) -> None:
    """Test if significant states are returned when including entities.

    We should only get back changes of the media_player.test entity.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {CONF_INCLUDE: {CONF_ENTITIES: ["media_player.test"]}},
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_include(hass_history) -> None:
    """Test significant states when including domains and entities.

    We should only get back changes of the media_player.test entity and the
    thermostat domain.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["script.can_cancel_this_one"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["thermostat"],
                    CONF_ENTITIES: ["media_player.test"],
                }
            },
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_include_exclude_domain(hass_history) -> None:
    """Test if significant states when excluding and including domains.

    We should get back all the media_player domain changes
    only since the include wins over the exclude but will
    exclude everything else.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {
                CONF_INCLUDE: {CONF_DOMAINS: ["media_player"]},
                CONF_EXCLUDE: {CONF_DOMAINS: ["media_player"]},
            },
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_include_exclude_entity(hass_history) -> None:
    """Test if significant states when excluding and including domains.

    We should not get back any changes since we include only
    media_player.test but also exclude it.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test2"]
    del states["media_player.test3"]
    del states["thermostat.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {
                CONF_INCLUDE: {CONF_ENTITIES: ["media_player.test"]},
                CONF_EXCLUDE: {CONF_ENTITIES: ["media_player.test"]},
            },
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_include_exclude(hass_history) -> None:
    """Test if significant states when in/excluding domains and entities.

    We should get back changes of the media_player.test2, media_player.test3,
    and thermostat.test.
    """
    hass = hass_history
    zero, four, states = record_states(hass)
    del states["media_player.test"]
    del states["thermostat.test2"]
    del states["script.can_cancel_this_one"]

    config = history.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            history.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["media_player"],
                    CONF_ENTITIES: ["thermostat.test"],
                },
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["thermostat"],
                    CONF_ENTITIES: ["media_player.test"],
                },
            },
        }
    )
    check_significant_states(hass, zero, four, states, config)


def test_get_significant_states_are_ordered(hass_history) -> None:
    """Test order of results from get_significant_states.

    When entity ids are given, the results should be returned with the data
    in the same order.
    """
    hass = hass_history
    zero, four, _states = record_states(hass)
    entity_ids = ["media_player.test", "media_player.test2"]
    hist = get_significant_states(
        hass, zero, four, entity_ids, filters=history.Filters()
    )
    assert list(hist.keys()) == entity_ids
    entity_ids = ["media_player.test2", "media_player.test"]
    hist = get_significant_states(
        hass, zero, four, entity_ids, filters=history.Filters()
    )
    assert list(hist.keys()) == entity_ids


def test_get_significant_states_only(hass_history) -> None:
    """Test significant states when significant_states_only is set."""
    hass = hass_history
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
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=start
    ):
        set_state("123", attributes={"attribute": 10.64})

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow",
        return_value=points[0],
    ):
        # Attributes are different, state not
        states.append(set_state("123", attributes={"attribute": 21.42}))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow",
        return_value=points[1],
    ):
        # state is different, attributes not
        states.append(set_state("32", attributes={"attribute": 21.42}))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow",
        return_value=points[2],
    ):
        # everything is different
        states.append(set_state("412", attributes={"attribute": 54.23}))

    hist = get_significant_states(hass, start, significant_changes_only=True)

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

    hist = get_significant_states(hass, start, significant_changes_only=False)

    assert len(hist[entity_id]) == 3
    assert_multiple_states_equal_without_context_and_last_changed(
        states, hist[entity_id]
    )


def check_significant_states(hass, zero, four, states, config):
    """Check if significant states are retrieved."""
    filters = history.Filters()
    exclude = config[history.DOMAIN].get(CONF_EXCLUDE)
    if exclude:
        filters.excluded_entities = exclude.get(CONF_ENTITIES, [])
        filters.excluded_domains = exclude.get(CONF_DOMAINS, [])
    include = config[history.DOMAIN].get(CONF_INCLUDE)
    if include:
        filters.included_entities = include.get(CONF_ENTITIES, [])
        filters.included_domains = include.get(CONF_DOMAINS, [])

    hist = get_significant_states(hass, zero, four, filters=filters)
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
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=one
    ):
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

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow",
        return_value=one + timedelta(microseconds=1),
    ):
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=two
    ):
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

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=three
    ):
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
    client = await hass_client()
    response = await client.get(f"/api/history/period/{dt_util.utcnow().isoformat()}")
    assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_use_include_order(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with include order."""
    await async_setup_component(
        hass, "history", {history.DOMAIN: {history.CONF_ORDER: True}}
    )
    client = await hass_client()
    response = await client.get(f"/api/history/period/{dt_util.utcnow().isoformat()}")
    assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_minimal_response(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
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
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history with no timestamp."""
    await async_setup_component(hass, "history", {})
    client = await hass_client()
    response = await client.get("/api/history/period")
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
    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}",
        params={"filter_entity_id": "non.existing,something.else"},
    )
    assert response.status == HTTPStatus.OK


async def test_fetch_period_api_with_entity_glob_include(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history."""
    await async_setup_component(
        hass,
        "history",
        {
            "history": {
                "include": {"entity_globs": ["light.k*"]},
            }
        },
    )
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.cow", "on")
    hass.states.async_set("light.nomatch", "on")

    await async_wait_recording_done(hass)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}",
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert response_json[0][0]["entity_id"] == "light.kitchen"


async def test_fetch_period_api_with_entity_glob_exclude(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history."""
    await async_setup_component(
        hass,
        "history",
        {
            "history": {
                "exclude": {
                    "entity_globs": ["light.k*", "binary_sensor.*_?"],
                    "domains": "switch",
                    "entities": "media_player.test",
                },
            }
        },
    )
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.cow", "on")
    hass.states.async_set("light.match", "on")
    hass.states.async_set("switch.match", "on")
    hass.states.async_set("media_player.test", "on")
    hass.states.async_set("binary_sensor.sensor_l", "on")
    hass.states.async_set("binary_sensor.sensor_r", "on")
    hass.states.async_set("binary_sensor.sensor", "on")

    await async_wait_recording_done(hass)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}",
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 3
    entities = {state[0]["entity_id"] for state in response_json}
    assert entities == {"binary_sensor.sensor", "light.cow", "light.match"}


async def test_fetch_period_api_with_entity_glob_include_and_exclude(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the fetch period view for history."""
    await async_setup_component(
        hass,
        "history",
        {
            "history": {
                "exclude": {
                    "entity_globs": ["light.many*", "binary_sensor.*"],
                },
                "include": {
                    "entity_globs": ["light.m*"],
                    "domains": "switch",
                    "entities": "media_player.test",
                },
            }
        },
    )
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.cow", "on")
    hass.states.async_set("light.match", "on")
    hass.states.async_set("light.many_state_changes", "on")
    hass.states.async_set("switch.match", "on")
    hass.states.async_set("media_player.test", "on")
    hass.states.async_set("binary_sensor.exclude", "on")

    await async_wait_recording_done(hass)

    client = await hass_client()
    response = await client.get(
        f"/api/history/period/{dt_util.utcnow().isoformat()}",
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 4
    entities = {state[0]["entity_id"] for state in response_json}
    assert entities == {
        "light.many_state_changes",
        "light.match",
        "media_player.test",
        "switch.match",
    }


async def test_entity_ids_limit_via_api(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
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
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
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


async def test_history_during_period(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert "a" not in sensor_test_history[1]
    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)

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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert "a" in sensor_test_history[1]
    assert sensor_test_history[1]["s"] == "off"
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)

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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
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
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)


async def test_history_during_period_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period bad state time."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
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

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "end_time": "dogs",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"
