"""The tests for the recorder filter matching the EntityFilter component."""
# pylint: disable=invalid-name
import json
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.engine.row import Row

from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.recorder.db_schema import EventData, Events, States
from homeassistant.components.recorder.filters import (
    Filters,
    extract_include_exclude_filter_conf,
    sqlalchemy_filter_from_include_exclude_conf,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entityfilter import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_GLOBS,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    convert_include_exclude_filter,
)

from .common import async_wait_recording_done, old_db_schema


# This test is for schema 37 and below (32 is new enough to test)
@pytest.fixture(autouse=True)
def db_schema_32():
    """Fixture to initialize the db with the old schema 32."""
    with old_db_schema("32"):
        yield


@pytest.fixture(name="legacy_recorder_mock")
async def legacy_recorder_mock_fixture(recorder_mock):
    """Fixture for legacy recorder mock."""
    with patch.object(recorder_mock.states_meta_manager, "active", False):
        yield recorder_mock


async def _async_get_states_and_events_with_filter(
    hass: HomeAssistant, sqlalchemy_filter: Filters, entity_ids: set[str]
) -> tuple[list[Row], list[Row]]:
    """Get states from the database based on a filter."""
    for entity_id in entity_ids:
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

    def _get_events_with_session():
        with session_scope(hass=hass) as session:
            return session.execute(
                select(EventData.shared_data)
                .outerjoin(Events, EventData.data_id == Events.data_id)
                .filter(sqlalchemy_filter.events_entity_filter())
            ).all()

    filtered_events_entity_ids = set()
    for row in await get_instance(hass).async_add_executor_job(
        _get_events_with_session
    ):
        event_data = json.loads(row[0])
        if ATTR_ENTITY_ID not in event_data:
            continue
        filtered_events_entity_ids.add(json.loads(row[0])[ATTR_ENTITY_ID])

    return filtered_states_entity_ids, filtered_events_entity_ids


async def test_included_and_excluded_simple_case_no_domains(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test filters with included and excluded without domains."""
    filter_accept = {"sensor.kitchen4", "switch.kitchen"}
    filter_reject = {
        "light.any",
        "switch.other",
        "cover.any",
        "sensor.weather5",
        "light.kitchen",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_ENTITY_GLOBS: ["sensor.kitchen*"],
            CONF_ENTITIES: ["switch.kitchen"],
        },
        CONF_EXCLUDE: {
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_and_excluded_simple_case_no_globs(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test filters with included and excluded without globs."""
    filter_accept = {"switch.bla", "sensor.blu", "sensor.keep"}
    filter_reject = {"sensor.bli"}
    conf = {
        CONF_INCLUDE: {
            CONF_DOMAINS: ["sensor", "homeassistant"],
            CONF_ENTITIES: ["switch.bla"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["switch"],
            CONF_ENTITIES: ["sensor.bli"],
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_and_excluded_simple_case_without_underscores(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_and_excluded_simple_case_with_underscores(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_and_excluded_complex_case(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_included_entities_and_excluded_domain(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test filters with included entities and excluded domain."""
    filter_accept = {
        "media_player.test",
        "media_player.test3",
        "thermostat.test",
        "zone.home",
        "script.can_cancel_this_one",
    }
    filter_reject = {
        "thermostat.test2",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_ENTITIES: ["media_player.test", "thermostat.test"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["thermostat"],
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_same_domain_included_excluded(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test filters with the same domain included and excluded."""
    filter_accept = {
        "media_player.test",
        "media_player.test3",
    }
    filter_reject = {
        "thermostat.test2",
        "thermostat.test",
        "zone.home",
        "script.can_cancel_this_one",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_DOMAINS: ["media_player"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["media_player"],
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_same_entity_included_excluded(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test filters with the same entity included and excluded."""
    filter_accept = {
        "media_player.test",
    }
    filter_reject = {
        "media_player.test3",
        "thermostat.test2",
        "thermostat.test",
        "zone.home",
        "script.can_cancel_this_one",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_ENTITIES: ["media_player.test"],
        },
        CONF_EXCLUDE: {
            CONF_ENTITIES: ["media_player.test"],
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_same_entity_included_excluded_include_domain_wins(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test filters with domain and entities and the include domain wins."""
    filter_accept = {
        "media_player.test2",
        "media_player.test3",
        "thermostat.test",
    }
    filter_reject = {
        "thermostat.test2",
        "zone.home",
        "script.can_cancel_this_one",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_DOMAINS: ["media_player"],
            CONF_ENTITIES: ["thermostat.test"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["thermostat"],
            CONF_ENTITIES: ["media_player.test"],
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_specificly_included_entity_always_wins(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test specificlly included entity always wins."""
    filter_accept = {
        "media_player.test2",
        "media_player.test3",
        "thermostat.test",
        "binary_sensor.specific_include",
    }
    filter_reject = {
        "binary_sensor.test2",
        "binary_sensor.home",
        "binary_sensor.can_cancel_this_one",
    }
    conf = {
        CONF_INCLUDE: {
            CONF_ENTITIES: ["binary_sensor.specific_include"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["binary_sensor"],
            CONF_ENTITY_GLOBS: ["binary_sensor.*"],
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)


async def test_specificly_included_entity_always_wins_over_glob(
    legacy_recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test specificlly included entity always wins over a glob."""
    filter_accept = {
        "sensor.apc900va_status",
        "sensor.apc900va_battery_charge",
        "sensor.apc900va_battery_runtime",
        "sensor.apc900va_load",
        "sensor.energy_x",
    }
    filter_reject = {
        "sensor.apc900va_not_included",
    }
    conf = {
        CONF_EXCLUDE: {
            CONF_DOMAINS: [
                "updater",
                "camera",
                "group",
                "media_player",
                "script",
                "sun",
                "automation",
                "zone",
                "weblink",
                "scene",
                "calendar",
                "weather",
                "remote",
                "notify",
                "switch",
                "shell_command",
                "media_player",
            ],
            CONF_ENTITY_GLOBS: ["sensor.apc900va_*"],
        },
        CONF_INCLUDE: {
            CONF_DOMAINS: [
                "binary_sensor",
                "climate",
                "device_tracker",
                "input_boolean",
                "sensor",
            ],
            CONF_ENTITY_GLOBS: ["sensor.energy_*"],
            CONF_ENTITIES: [
                "sensor.apc900va_status",
                "sensor.apc900va_battery_charge",
                "sensor.apc900va_battery_runtime",
                "sensor.apc900va_load",
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

    (
        filtered_states_entity_ids,
        filtered_events_entity_ids,
    ) = await _async_get_states_and_events_with_filter(
        hass, sqlalchemy_filter, filter_accept | filter_reject
    )

    assert filtered_states_entity_ids == filter_accept
    assert not filtered_states_entity_ids.intersection(filter_reject)

    assert filtered_events_entity_ids == filter_accept
    assert not filtered_events_entity_ids.intersection(filter_reject)
