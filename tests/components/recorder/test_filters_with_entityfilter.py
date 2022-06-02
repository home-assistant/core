"""The tests for the recorder filter matching the EntityFilter component."""
import json

from sqlalchemy import select

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.filters import (
    extract_include_exclude_filter_conf,
    sqlalchemy_filter_from_include_exclude_conf,
)
from homeassistant.components.recorder.models import EventData, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.helpers.entityfilter import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_GLOBS,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    convert_include_exclude_filter,
)

from .common import async_wait_recording_done


async def test_included_and_excluded_simple_case_without_underscores(
    hass, recorder_mock
):
    """Test filters with included and excluded without underscores."""
    filter_accept = {"light.any", "sensor.kitchen4", "switch.kitchen"}
    filter_reject = {"switch.other", "cover.any", "sensor.weather5", "light.kitchen"}
    conf = {
        CONF_INCLUDE: {
            CONF_DOMAINS: ["light"],
            CONF_ENTITY_GLOBS: ["sensor.kitchen*"],
            CONF_ENTITIES: ["switch.kitchen"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["cover"],
            CONF_ENTITY_GLOBS: ["sensor.weather*"],
            CONF_ENTITIES: ["light.kitchen"],
        },
    }

    extracted_filter = extract_include_exclude_filter_conf(conf)
    entity_filter = convert_include_exclude_filter(extracted_filter)
    sqlalchemy_filter = sqlalchemy_filter_from_include_exclude_conf(extracted_filter)
    assert sqlalchemy_filter is not None

    for entity_id in filter_accept:
        assert entity_filter(entity_id) is True

    for entity_id in filter_reject:
        assert entity_filter(entity_id) is False

    assert not entity_filter.explicitly_included("light.any")
    assert not entity_filter.explicitly_included("switch.other")
    assert entity_filter.explicitly_included("sensor.kitchen4")
    assert entity_filter.explicitly_included("switch.kitchen")

    assert not entity_filter.explicitly_excluded("light.any")
    assert not entity_filter.explicitly_excluded("switch.other")
    assert entity_filter.explicitly_excluded("sensor.weather5")
    assert entity_filter.explicitly_excluded("light.kitchen")

    for entity_id in filter_accept | filter_reject:
        hass.states.async_set(entity_id, STATE_ON)
        hass.bus.async_fire("any", {ATTR_ENTITY_ID: entity_id})

    await async_wait_recording_done(hass)

    def _get_states_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(States.entity_id).filter(
                    sqlalchemy_filter.states_entity_filter()
                )
            ).all()

    filtered_states_entity_ids = {
        row[0]
        for row in await get_instance(hass).async_add_executor_job(
            _get_states_with_session
        )
    }

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    def _get_events_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(EventData.shared_data).filter(
                    sqlalchemy_filter.events_entity_filter()
                )
            ).all()

    filtered_events_entity_ids = set()
    for row in await get_instance(hass).async_add_executor_job(
        _get_events_with_session
    ):
        event_data = json.loads(row[0])
        if ATTR_ENTITY_ID not in event_data:
            continue
        filtered_events_entity_ids.add(json.loads(row[0])[ATTR_ENTITY_ID])

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_and_excluded_simple_case_with_underscores(hass, recorder_mock):
    """Test filters with included and excluded with underscores."""
    filter_accept = {"light.any", "sensor.kitchen_4", "switch.kitchen"}
    filter_reject = {"switch.other", "cover.any", "sensor.weather_5", "light.kitchen"}
    conf = {
        CONF_INCLUDE: {
            CONF_DOMAINS: ["light"],
            CONF_ENTITY_GLOBS: ["sensor.kitchen_*"],
            CONF_ENTITIES: ["switch.kitchen"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["cover"],
            CONF_ENTITY_GLOBS: ["sensor.weather_*"],
            CONF_ENTITIES: ["light.kitchen"],
        },
    }

    extracted_filter = extract_include_exclude_filter_conf(conf)
    entity_filter = convert_include_exclude_filter(extracted_filter)
    sqlalchemy_filter = sqlalchemy_filter_from_include_exclude_conf(extracted_filter)
    assert sqlalchemy_filter is not None

    for entity_id in filter_accept:
        assert entity_filter(entity_id) is True

    for entity_id in filter_reject:
        assert entity_filter(entity_id) is False

    assert not entity_filter.explicitly_included("light.any")
    assert not entity_filter.explicitly_included("switch.other")
    assert entity_filter.explicitly_included("sensor.kitchen_4")
    assert entity_filter.explicitly_included("switch.kitchen")

    assert not entity_filter.explicitly_excluded("light.any")
    assert not entity_filter.explicitly_excluded("switch.other")
    assert entity_filter.explicitly_excluded("sensor.weather_5")
    assert entity_filter.explicitly_excluded("light.kitchen")

    for entity_id in filter_accept | filter_reject:
        hass.states.async_set(entity_id, STATE_ON)
        hass.bus.async_fire("any", {ATTR_ENTITY_ID: entity_id})

    await async_wait_recording_done(hass)

    def _get_states_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(States.entity_id).filter(
                    sqlalchemy_filter.states_entity_filter()
                )
            ).all()

    filtered_states_entity_ids = {
        row[0]
        for row in await get_instance(hass).async_add_executor_job(
            _get_states_with_session
        )
    }

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    def _get_events_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(EventData.shared_data).filter(
                    sqlalchemy_filter.events_entity_filter()
                )
            ).all()

    filtered_events_entity_ids = set()
    for row in await get_instance(hass).async_add_executor_job(
        _get_events_with_session
    ):
        event_data = json.loads(row[0])
        if ATTR_ENTITY_ID not in event_data:
            continue
        filtered_events_entity_ids.add(json.loads(row[0])[ATTR_ENTITY_ID])

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_and_excluded_complex_case(hass, recorder_mock):
    """Test filters with included and excluded with a complex filter."""
    filter_accept = {"light.any", "sensor.kitchen_4", "switch.kitchen"}
    filter_reject = {
        "camera.one",
        "notify.any",
        "automation.update_readme",
        "automation.update_utilities_cost",
        "binary_sensor.iss",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_ENTITIES: ["group.trackers"],
        },
        CONF_EXCLUDE: {
            CONF_ENTITIES: [
                "automation.update_readme",
                "automation.update_utilities_cost",
                "binary_sensor.iss",
            ],
            CONF_DOMAINS: [
                "camera",
                "group",
                "media_player",
                "notify",
                "scene",
                "sun",
                "zone",
            ],
        },
    }

    extracted_filter = extract_include_exclude_filter_conf(conf)
    entity_filter = convert_include_exclude_filter(extracted_filter)
    sqlalchemy_filter = sqlalchemy_filter_from_include_exclude_conf(extracted_filter)
    assert sqlalchemy_filter is not None

    for entity_id in filter_accept:
        assert entity_filter(entity_id) is True

    for entity_id in filter_reject:
        assert entity_filter(entity_id) is False

    for entity_id in filter_accept | filter_reject:
        hass.states.async_set(entity_id, STATE_ON)
        hass.bus.async_fire("any", {ATTR_ENTITY_ID: entity_id})

    await async_wait_recording_done(hass)

    def _get_states_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(States.entity_id).filter(
                    sqlalchemy_filter.states_entity_filter()
                )
            ).all()

    filtered_states_entity_ids = {
        row[0]
        for row in await get_instance(hass).async_add_executor_job(
            _get_states_with_session
        )
    }

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    def _get_events_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(EventData.shared_data).filter(
                    sqlalchemy_filter.events_entity_filter()
                )
            ).all()

    filtered_events_entity_ids = set()
    for row in await get_instance(hass).async_add_executor_job(
        _get_events_with_session
    ):
        event_data = json.loads(row[0])
        if ATTR_ENTITY_ID not in event_data:
            continue
        filtered_events_entity_ids.add(json.loads(row[0])[ATTR_ENTITY_ID])

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)
