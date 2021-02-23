"""The tests for the logbook component."""
# pylint: disable=protected-access,invalid-name
import collections
from datetime import datetime, timedelta
import json
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant.components import logbook, recorder
from homeassistant.components.alexa.smart_home import EVENT_ALEXA_SMART_HOME
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.recorder.models import process_timestamp_to_utc_isoformat
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    ATTR_SERVICE,
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.helpers.entityfilter import CONF_ENTITY_GLOBS
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, init_recorder_component, mock_platform
from tests.components.recorder.common import trigger_db_commit

EMPTY_CONFIG = logbook.CONFIG_SCHEMA({logbook.DOMAIN: {}})


@pytest.fixture
def hass_():
    """Set up things to be run when tests are started."""
    hass = get_test_home_assistant()
    init_recorder_component(hass)  # Force an in memory DB
    with patch("homeassistant.components.http.start_http_server_and_save_config"):
        assert setup_component(hass, logbook.DOMAIN, EMPTY_CONFIG)
        yield hass
    hass.stop()


def test_service_call_create_logbook_entry(hass_):
    """Test if service call create log book entry."""
    calls = []

    @ha.callback
    def event_listener(event):
        """Append on event."""
        calls.append(event)

    hass_.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)
    hass_.services.call(
        logbook.DOMAIN,
        "log",
        {
            logbook.ATTR_NAME: "Alarm",
            logbook.ATTR_MESSAGE: "is triggered",
            logbook.ATTR_DOMAIN: "switch",
            logbook.ATTR_ENTITY_ID: "switch.test_switch",
        },
        True,
    )
    hass_.services.call(
        logbook.DOMAIN,
        "log",
        {
            logbook.ATTR_NAME: "This entry",
            logbook.ATTR_MESSAGE: "has no domain or entity_id",
        },
        True,
    )
    # Logbook entry service call results in firing an event.
    # Our service call will unblock when the event listeners have been
    # scheduled. This means that they may not have been processed yet.
    trigger_db_commit(hass_)
    hass_.block_till_done()
    hass_.data[recorder.DATA_INSTANCE].block_till_done()

    events = list(
        logbook._get_events(
            hass_,
            dt_util.utcnow() - timedelta(hours=1),
            dt_util.utcnow() + timedelta(hours=1),
        )
    )
    assert len(events) == 2

    assert len(calls) == 2
    first_call = calls[-2]

    assert first_call.data.get(logbook.ATTR_NAME) == "Alarm"
    assert first_call.data.get(logbook.ATTR_MESSAGE) == "is triggered"
    assert first_call.data.get(logbook.ATTR_DOMAIN) == "switch"
    assert first_call.data.get(logbook.ATTR_ENTITY_ID) == "switch.test_switch"

    last_call = calls[-1]

    assert last_call.data.get(logbook.ATTR_NAME) == "This entry"
    assert last_call.data.get(logbook.ATTR_MESSAGE) == "has no domain or entity_id"
    assert last_call.data.get(logbook.ATTR_DOMAIN) == "logbook"


def test_service_call_create_log_book_entry_no_message(hass_):
    """Test if service call create log book entry without message."""
    calls = []

    @ha.callback
    def event_listener(event):
        """Append on event."""
        calls.append(event)

    hass_.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)

    with pytest.raises(vol.Invalid):
        hass_.services.call(logbook.DOMAIN, "log", {}, True)

    # Logbook entry service call results in firing an event.
    # Our service call will unblock when the event listeners have been
    # scheduled. This means that they may not have been processed yet.
    hass_.block_till_done()

    assert len(calls) == 0


def test_humanify_filter_sensor(hass_):
    """Test humanify filter too frequent sensor values."""
    entity_id = "sensor.bla"

    pointA = dt_util.utcnow().replace(minute=2)
    pointB = pointA.replace(minute=5)
    pointC = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)
    entity_attr_cache = logbook.EntityAttributeCache(hass_)

    eventA = create_state_changed_event(pointA, entity_id, 10)
    eventB = create_state_changed_event(pointB, entity_id, 20)
    eventC = create_state_changed_event(pointC, entity_id, 30)

    entries = list(
        logbook.humanify(hass_, (eventA, eventB, eventC), entity_attr_cache, {})
    )

    assert len(entries) == 2
    assert_entry(entries[0], pointB, "bla", entity_id=entity_id)

    assert_entry(entries[1], pointC, "bla", entity_id=entity_id)


def test_home_assistant_start_stop_grouped(hass_):
    """Test if HA start and stop events are grouped.

    Events that are occurring in the same minute.
    """
    entity_attr_cache = logbook.EntityAttributeCache(hass_)
    entries = list(
        logbook.humanify(
            hass_,
            (
                MockLazyEventPartialState(EVENT_HOMEASSISTANT_STOP),
                MockLazyEventPartialState(EVENT_HOMEASSISTANT_START),
            ),
            entity_attr_cache,
            {},
        ),
    )

    assert len(entries) == 1
    assert_entry(
        entries[0], name="Home Assistant", message="restarted", domain=ha.DOMAIN
    )


def test_home_assistant_start(hass_):
    """Test if HA start is not filtered or converted into a restart."""
    entity_id = "switch.bla"
    pointA = dt_util.utcnow()
    entity_attr_cache = logbook.EntityAttributeCache(hass_)

    entries = list(
        logbook.humanify(
            hass_,
            (
                MockLazyEventPartialState(EVENT_HOMEASSISTANT_START),
                create_state_changed_event(pointA, entity_id, 10),
            ),
            entity_attr_cache,
            {},
        )
    )

    assert len(entries) == 2
    assert_entry(entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN)
    assert_entry(entries[1], pointA, "bla", entity_id=entity_id)


def test_process_custom_logbook_entries(hass_):
    """Test if custom log book entries get added as an entry."""
    name = "Nice name"
    message = "has a custom entry"
    entity_id = "sun.sun"
    entity_attr_cache = logbook.EntityAttributeCache(hass_)

    entries = list(
        logbook.humanify(
            hass_,
            (
                MockLazyEventPartialState(
                    logbook.EVENT_LOGBOOK_ENTRY,
                    {
                        logbook.ATTR_NAME: name,
                        logbook.ATTR_MESSAGE: message,
                        logbook.ATTR_ENTITY_ID: entity_id,
                    },
                ),
            ),
            entity_attr_cache,
            {},
        )
    )

    assert len(entries) == 1
    assert_entry(entries[0], name=name, message=message, entity_id=entity_id)


# pylint: disable=no-self-use
def assert_entry(
    entry, when=None, name=None, message=None, domain=None, entity_id=None
):
    """Assert an entry is what is expected."""
    return _assert_entry(entry, when, name, message, domain, entity_id)


def create_state_changed_event(
    event_time_fired,
    entity_id,
    state,
    attributes=None,
    last_changed=None,
    last_updated=None,
):
    """Create state changed event."""
    old_state = ha.State(
        entity_id, "old", attributes, last_changed, last_updated
    ).as_dict()
    new_state = ha.State(
        entity_id, state, attributes, last_changed, last_updated
    ).as_dict()

    return create_state_changed_event_from_old_new(
        entity_id, event_time_fired, old_state, new_state
    )


# pylint: disable=no-self-use
def create_state_changed_event_from_old_new(
    entity_id, event_time_fired, old_state, new_state
):
    """Create a state changed event from a old and new state."""
    attributes = {}
    if new_state is not None:
        attributes = new_state.get("attributes")
    attributes_json = json.dumps(attributes, cls=JSONEncoder)
    row = collections.namedtuple(
        "Row",
        [
            "event_type"
            "event_data"
            "time_fired"
            "context_id"
            "context_user_id"
            "context_parent_id"
            "state"
            "entity_id"
            "domain"
            "attributes"
            "state_id",
            "old_state_id",
        ],
    )

    row.event_type = EVENT_STATE_CHANGED
    row.event_data = "{}"
    row.attributes = attributes_json
    row.time_fired = event_time_fired
    row.state = new_state and new_state.get("state")
    row.entity_id = entity_id
    row.domain = entity_id and ha.split_entity_id(entity_id)[0]
    row.context_id = None
    row.context_user_id = None
    row.context_parent_id = None
    row.old_state_id = old_state and 1
    row.state_id = new_state and 1
    return logbook.LazyEventPartialState(row)


async def test_logbook_view(hass, hass_client):
    """Test the logbook view."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    client = await hass_client()
    response = await client.get(f"/api/logbook/{dt_util.utcnow().isoformat()}")
    assert response.status == 200


async def test_logbook_view_period_entity(hass, hass_client):
    """Test the logbook view with period and entity."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "switch.second"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_second

    # Test today entries with filter by period
    response = await client.get(f"/api/logbook/{start_date.isoformat()}?period=1")
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_second

    # Test today entries with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?entity=switch.test"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test

    # Test entries for 3 days with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?period=3&entity=switch.test"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test

    # Tomorrow time 00:00:00
    start = (dt_util.utcnow() + timedelta(days=1)).date()
    start_date = datetime(start.year, start.month, start.day)

    # Test tomorrow entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 0

    # Test tomorrow entries with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?entity=switch.test"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 0

    # Test entries from tomorrow to 3 days ago with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?period=3&entity=switch.test"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test


async def test_logbook_describe_event(hass, hass_client):
    """Test teaching logbook about a new event."""
    await hass.async_add_executor_job(init_recorder_component, hass)

    def _describe(event):
        """Describe an event."""
        return {"name": "Test Name", "message": "tested a message"}

    hass.config.components.add("fake_integration")
    mock_platform(
        hass,
        "fake_integration.logbook",
        Mock(
            async_describe_events=lambda hass, async_describe_event: async_describe_event(
                "test_domain", "some_event", _describe
            )
        ),
    )

    assert await async_setup_component(hass, "logbook", {})
    with patch(
        "homeassistant.util.dt.utcnow",
        return_value=dt_util.utcnow() - timedelta(seconds=5),
    ):
        hass.bus.async_fire("some_event")
        await hass.async_block_till_done()
        await hass.async_add_executor_job(trigger_db_commit, hass)
        await hass.async_block_till_done()
        await hass.async_add_executor_job(
            hass.data[recorder.DATA_INSTANCE].block_till_done
        )

    client = await hass_client()
    response = await client.get("/api/logbook")
    results = await response.json()
    assert len(results) == 1
    event = results[0]
    assert event["name"] == "Test Name"
    assert event["message"] == "tested a message"
    assert event["domain"] == "test_domain"


async def test_exclude_described_event(hass, hass_client):
    """Test exclusions of events that are described by another integration."""
    name = "My Automation Rule"
    entity_id = "automation.excluded_rule"
    entity_id2 = "automation.included_rule"
    entity_id3 = "sensor.excluded_domain"

    def _describe(event):
        """Describe an event."""
        return {
            "name": "Test Name",
            "message": "tested a message",
            "entity_id": event.data.get(ATTR_ENTITY_ID),
        }

    def async_describe_events(hass, async_describe_event):
        """Mock to describe events."""
        async_describe_event("automation", "some_automation_event", _describe)
        async_describe_event("sensor", "some_event", _describe)

    hass.config.components.add("fake_integration")
    mock_platform(
        hass,
        "fake_integration.logbook",
        Mock(async_describe_events=async_describe_events),
    )

    await hass.async_add_executor_job(init_recorder_component, hass)
    assert await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {
                CONF_EXCLUDE: {CONF_DOMAINS: ["sensor"], CONF_ENTITIES: [entity_id]}
            }
        },
    )

    with patch(
        "homeassistant.util.dt.utcnow",
        return_value=dt_util.utcnow() - timedelta(seconds=5),
    ):
        hass.bus.async_fire(
            "some_automation_event",
            {logbook.ATTR_NAME: name, logbook.ATTR_ENTITY_ID: entity_id},
        )
        hass.bus.async_fire(
            "some_automation_event",
            {logbook.ATTR_NAME: name, logbook.ATTR_ENTITY_ID: entity_id2},
        )
        hass.bus.async_fire(
            "some_event", {logbook.ATTR_NAME: name, logbook.ATTR_ENTITY_ID: entity_id3}
        )
        await hass.async_block_till_done()
        await hass.async_add_executor_job(trigger_db_commit, hass)
        await hass.async_block_till_done()
        await hass.async_add_executor_job(
            hass.data[recorder.DATA_INSTANCE].block_till_done
        )

    client = await hass_client()
    response = await client.get("/api/logbook")
    results = await response.json()
    assert len(results) == 1
    event = results[0]
    assert event["name"] == "Test Name"
    assert event["entity_id"] == "automation.included_rule"


async def test_logbook_view_end_time_entity(hass, hass_client):
    """Test the logbook view with end_time and entity."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "switch.second"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_second

    # Test entries for 3 days with filter by entity_id
    end_time = start + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test

    # Tomorrow time 00:00:00
    start = dt_util.utcnow()
    start_date = datetime(start.year, start.month, start.day)

    # Test entries from today to 3 days with filter by entity_id
    end_time = start_date + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test"
    )
    assert response.status == 200
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test


async def test_logbook_entity_filter_with_automations(hass, hass_client):
    """Test the logbook view with end_time and entity with automations and scripts."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await async_setup_component(hass, "automation", {})
    await async_setup_component(hass, "script", {})

    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = "alarm_control_panel.area_001"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "alarm_control_panel.area_002"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)

    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation", ATTR_ENTITY_ID: "automation.mock_automation"},
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    json_dict = await response.json()

    assert json_dict[0]["entity_id"] == entity_id_test
    assert json_dict[1]["entity_id"] == entity_id_second
    assert json_dict[2]["entity_id"] == "automation.mock_automation"
    assert json_dict[3]["entity_id"] == "script.mock_script"
    assert json_dict[4]["domain"] == "homeassistant"

    # Test entries for 3 days with filter by entity_id
    end_time = start + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=alarm_control_panel.area_001"
    )
    assert response.status == 200
    json_dict = await response.json()
    assert len(json_dict) == 1
    assert json_dict[0]["entity_id"] == entity_id_test

    # Tomorrow time 00:00:00
    start = dt_util.utcnow()
    start_date = datetime(start.year, start.month, start.day)

    # Test entries from today to 3 days with filter by entity_id
    end_time = start_date + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=alarm_control_panel.area_002"
    )
    assert response.status == 200
    json_dict = await response.json()
    assert len(json_dict) == 1
    assert json_dict[0]["entity_id"] == entity_id_second


async def test_filter_continuous_sensor_values(hass, hass_client):
    """Test remove continuous sensor events from logbook."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "sensor.bla"
    hass.states.async_set(entity_id_second, STATE_OFF, {"unit_of_measurement": "foo"})
    hass.states.async_set(entity_id_second, STATE_ON, {"unit_of_measurement": "foo"})
    entity_id_third = "light.bla"
    hass.states.async_set(entity_id_third, STATE_OFF, {"unit_of_measurement": "foo"})
    hass.states.async_set(entity_id_third, STATE_ON, {"unit_of_measurement": "foo"})

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    response_json = await response.json()

    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_third


async def test_exclude_new_entities(hass, hass_client):
    """Test if events are excluded on first update."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id = "climate.bla"
    entity_id2 = "climate.blu"

    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set(entity_id2, STATE_ON)
    hass.states.async_set(entity_id2, STATE_OFF)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    response_json = await response.json()

    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id2
    assert response_json[1]["domain"] == "homeassistant"
    assert response_json[1]["message"] == "started"


async def test_exclude_removed_entities(hass, hass_client):
    """Test if events are excluded on last update."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id = "climate.bla"
    entity_id2 = "climate.blu"

    hass.states.async_set(entity_id, STATE_ON)
    hass.states.async_set(entity_id, STATE_OFF)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set(entity_id2, STATE_ON)
    hass.states.async_set(entity_id2, STATE_OFF)

    hass.states.async_remove(entity_id)
    hass.states.async_remove(entity_id2)

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    response_json = await response.json()

    assert len(response_json) == 3
    assert response_json[0]["entity_id"] == entity_id
    assert response_json[1]["domain"] == "homeassistant"
    assert response_json[1]["message"] == "started"
    assert response_json[2]["entity_id"] == entity_id2


async def test_exclude_attribute_changes(hass, hass_client):
    """Test if events of attribute changes are filtered."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set("light.kitchen", STATE_OFF)
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 100})
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 200})
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 300})
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 400})
    hass.states.async_set("light.kitchen", STATE_OFF)

    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    response_json = await response.json()

    assert len(response_json) == 3
    assert response_json[0]["domain"] == "homeassistant"
    assert response_json[1]["entity_id"] == "light.kitchen"
    assert response_json[2]["entity_id"] == "light.kitchen"


async def test_logbook_entity_context_id(hass, hass_client):
    """Test the logbook view with end_time and entity with automations and scripts."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await async_setup_component(hass, "automation", {})
    await async_setup_component(hass, "script", {})

    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    context = ha.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )

    # An Automation
    automation_entity_id_test = "automation.alarm"
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation", ATTR_ENTITY_ID: automation_entity_id_test},
        context=context,
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
        context=context,
    )
    hass.states.async_set(
        automation_entity_id_test,
        STATE_ON,
        {ATTR_FRIENDLY_NAME: "Alarm Automation"},
        context=context,
    )

    entity_id_test = "alarm_control_panel.area_001"
    hass.states.async_set(entity_id_test, STATE_OFF, context=context)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id_test, STATE_ON, context=context)
    await hass.async_block_till_done()
    entity_id_second = "alarm_control_panel.area_002"
    hass.states.async_set(entity_id_second, STATE_OFF, context=context)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id_second, STATE_ON, context=context)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    await hass.async_add_executor_job(
        logbook.log_entry,
        hass,
        "mock_name",
        "mock_message",
        "alarm_control_panel",
        "alarm_control_panel.area_003",
        context,
    )
    await hass.async_block_till_done()

    await hass.async_add_executor_job(
        logbook.log_entry,
        hass,
        "mock_name",
        "mock_message",
        "homeassistant",
        None,
        context,
    )
    await hass.async_block_till_done()

    # A service call
    light_turn_off_service_context = ha.Context(
        id="9c5bd62de45711eaaeb351041eec8dd9",
        user_id="9400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set("light.switch", STATE_ON)
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_CALL_SERVICE,
        {
            ATTR_DOMAIN: "light",
            ATTR_SERVICE: "turn_off",
            ATTR_ENTITY_ID: "light.switch",
        },
        context=light_turn_off_service_context,
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "light.switch", STATE_OFF, context=light_turn_off_service_context
    )
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    json_dict = await response.json()

    assert json_dict[0]["entity_id"] == "automation.alarm"
    assert "context_entity_id" not in json_dict[0]
    assert json_dict[0]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[1]["entity_id"] == "script.mock_script"
    assert json_dict[1]["context_event_type"] == "automation_triggered"
    assert json_dict[1]["context_entity_id"] == "automation.alarm"
    assert json_dict[1]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[1]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[2]["entity_id"] == entity_id_test
    assert json_dict[2]["context_event_type"] == "automation_triggered"
    assert json_dict[2]["context_entity_id"] == "automation.alarm"
    assert json_dict[2]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[2]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == entity_id_second
    assert json_dict[3]["context_event_type"] == "automation_triggered"
    assert json_dict[3]["context_entity_id"] == "automation.alarm"
    assert json_dict[3]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[3]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[4]["domain"] == "homeassistant"

    assert json_dict[5]["entity_id"] == "alarm_control_panel.area_003"
    assert json_dict[5]["context_event_type"] == "automation_triggered"
    assert json_dict[5]["context_entity_id"] == "automation.alarm"
    assert json_dict[5]["domain"] == "alarm_control_panel"
    assert json_dict[5]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[5]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[6]["domain"] == "homeassistant"
    assert json_dict[6]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[7]["entity_id"] == "light.switch"
    assert json_dict[7]["context_event_type"] == "call_service"
    assert json_dict[7]["context_domain"] == "light"
    assert json_dict[7]["context_service"] == "turn_off"
    assert json_dict[7]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_logbook_entity_context_parent_id(hass, hass_client):
    """Test the logbook view links events via context parent_id."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await async_setup_component(hass, "automation", {})
    await async_setup_component(hass, "script", {})

    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    context = ha.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )

    # An Automation triggering scripts with a new context
    automation_entity_id_test = "automation.alarm"
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation", ATTR_ENTITY_ID: automation_entity_id_test},
        context=context,
    )

    child_context = ha.Context(
        id="2798bfedf8234b5e9f4009c91f48f30c",
        parent_id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
        context=child_context,
    )
    hass.states.async_set(
        automation_entity_id_test,
        STATE_ON,
        {ATTR_FRIENDLY_NAME: "Alarm Automation"},
        context=child_context,
    )

    entity_id_test = "alarm_control_panel.area_001"
    hass.states.async_set(entity_id_test, STATE_OFF, context=child_context)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id_test, STATE_ON, context=child_context)
    await hass.async_block_till_done()
    entity_id_second = "alarm_control_panel.area_002"
    hass.states.async_set(entity_id_second, STATE_OFF, context=child_context)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id_second, STATE_ON, context=child_context)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    logbook.async_log_entry(
        hass,
        "mock_name",
        "mock_message",
        "alarm_control_panel",
        "alarm_control_panel.area_003",
        child_context,
    )
    await hass.async_block_till_done()

    logbook.async_log_entry(
        hass,
        "mock_name",
        "mock_message",
        "homeassistant",
        None,
        child_context,
    )
    await hass.async_block_till_done()

    # A state change via service call with the script as the parent
    light_turn_off_service_context = ha.Context(
        id="9c5bd62de45711eaaeb351041eec8dd9",
        parent_id="2798bfedf8234b5e9f4009c91f48f30c",
        user_id="9400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set("light.switch", STATE_ON)
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_CALL_SERVICE,
        {
            ATTR_DOMAIN: "light",
            ATTR_SERVICE: "turn_off",
            ATTR_ENTITY_ID: "light.switch",
        },
        context=light_turn_off_service_context,
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "light.switch", STATE_OFF, context=light_turn_off_service_context
    )
    await hass.async_block_till_done()

    # An event with a parent event, but the parent event isn't available
    missing_parent_context = ha.Context(
        id="fc40b9a0d1f246f98c34b33c76228ee6",
        parent_id="c8ce515fe58e442f8664246c65ed964f",
        user_id="485cacf93ef84d25a99ced3126b921d2",
    )
    logbook.async_log_entry(
        hass,
        "mock_name",
        "mock_message",
        "alarm_control_panel",
        "alarm_control_panel.area_009",
        missing_parent_context,
    )
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    json_dict = await response.json()

    assert json_dict[0]["entity_id"] == "automation.alarm"
    assert "context_entity_id" not in json_dict[0]
    assert json_dict[0]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    # New context, so this looks to be triggered by the Alarm Automation
    assert json_dict[1]["entity_id"] == "script.mock_script"
    assert json_dict[1]["context_event_type"] == "automation_triggered"
    assert json_dict[1]["context_entity_id"] == "automation.alarm"
    assert json_dict[1]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[1]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[2]["entity_id"] == entity_id_test
    assert json_dict[2]["context_event_type"] == "script_started"
    assert json_dict[2]["context_entity_id"] == "script.mock_script"
    assert json_dict[2]["context_entity_id_name"] == "mock script"
    assert json_dict[2]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == entity_id_second
    assert json_dict[3]["context_event_type"] == "script_started"
    assert json_dict[3]["context_entity_id"] == "script.mock_script"
    assert json_dict[3]["context_entity_id_name"] == "mock script"
    assert json_dict[3]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[4]["domain"] == "homeassistant"

    assert json_dict[5]["entity_id"] == "alarm_control_panel.area_003"
    assert json_dict[5]["context_event_type"] == "script_started"
    assert json_dict[5]["context_entity_id"] == "script.mock_script"
    assert json_dict[5]["domain"] == "alarm_control_panel"
    assert json_dict[5]["context_entity_id_name"] == "mock script"
    assert json_dict[5]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[6]["domain"] == "homeassistant"
    assert json_dict[6]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[7]["entity_id"] == "light.switch"
    assert json_dict[7]["context_event_type"] == "call_service"
    assert json_dict[7]["context_domain"] == "light"
    assert json_dict[7]["context_service"] == "turn_off"
    assert json_dict[7]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    assert json_dict[8]["entity_id"] == "alarm_control_panel.area_009"
    assert json_dict[8]["domain"] == "alarm_control_panel"
    assert "context_event_type" not in json_dict[8]
    assert "context_entity_id" not in json_dict[8]
    assert "context_entity_id_name" not in json_dict[8]
    assert json_dict[8]["context_user_id"] == "485cacf93ef84d25a99ced3126b921d2"


async def test_logbook_context_from_template(hass, hass_client):
    """Test the logbook view with end_time and entity with automations and scripts."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        "value_template": "{{ states.switch.test_state.state }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            }
        },
    )
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Entity added (should not be logged)
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    # First state change (should be logged)
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    switch_turn_off_context = ha.Context(
        id="9c5bd62de45711eaaeb351041eec8dd9",
        user_id="9400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set(
        "switch.test_state", STATE_ON, context=switch_turn_off_context
    )
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    json_dict = await response.json()

    assert json_dict[0]["domain"] == "homeassistant"
    assert "context_entity_id" not in json_dict[0]

    assert json_dict[1]["entity_id"] == "switch.test_template_switch"

    assert json_dict[2]["entity_id"] == "switch.test_state"

    assert json_dict[3]["entity_id"] == "switch.test_template_switch"
    assert json_dict[3]["context_entity_id"] == "switch.test_state"
    assert json_dict[3]["context_entity_id_name"] == "test state"

    assert json_dict[4]["entity_id"] == "switch.test_state"
    assert json_dict[4]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    assert json_dict[5]["entity_id"] == "switch.test_template_switch"
    assert json_dict[5]["context_entity_id"] == "switch.test_state"
    assert json_dict[5]["context_entity_id_name"] == "test state"
    assert json_dict[5]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_logbook_entity_matches_only(hass, hass_client):
    """Test the logbook view with a single entity and entity_matches_only."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        "value_template": "{{ states.switch.test_state.state }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            }
        },
    )
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Entity added (should not be logged)
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    # First state change (should be logged)
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    switch_turn_off_context = ha.Context(
        id="9c5bd62de45711eaaeb351041eec8dd9",
        user_id="9400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set(
        "switch.test_state", STATE_ON, context=switch_turn_off_context
    )
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test_state&entity_matches_only"
    )
    assert response.status == 200
    json_dict = await response.json()

    assert len(json_dict) == 2

    assert json_dict[0]["entity_id"] == "switch.test_state"

    assert json_dict[1]["entity_id"] == "switch.test_state"
    assert json_dict[1]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_logbook_entity_matches_only_multiple(hass, hass_client):
    """Test the logbook view with a multiple entities and entity_matches_only."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        "value_template": "{{ states.switch.test_state.state }}",
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                    }
                },
            }
        },
    )
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Entity added (should not be logged)
    hass.states.async_set("switch.test_state", STATE_ON)
    hass.states.async_set("light.test_state", STATE_ON)

    await hass.async_block_till_done()

    # First state change (should be logged)
    hass.states.async_set("switch.test_state", STATE_OFF)
    hass.states.async_set("light.test_state", STATE_OFF)

    await hass.async_block_till_done()

    switch_turn_off_context = ha.Context(
        id="9c5bd62de45711eaaeb351041eec8dd9",
        user_id="9400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set(
        "switch.test_state", STATE_ON, context=switch_turn_off_context
    )
    hass.states.async_set("light.test_state", STATE_ON, context=switch_turn_off_context)
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test_state,light.test_state&entity_matches_only"
    )
    assert response.status == 200
    json_dict = await response.json()

    assert len(json_dict) == 4

    assert json_dict[0]["entity_id"] == "switch.test_state"

    assert json_dict[1]["entity_id"] == "light.test_state"

    assert json_dict[2]["entity_id"] == "switch.test_state"
    assert json_dict[2]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == "light.test_state"
    assert json_dict[3]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_logbook_invalid_entity(hass, hass_client):
    """Test the logbook view with requesting an invalid entity."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()
    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=invalid&entity_matches_only"
    )
    assert response.status == 500


async def test_icon_and_state(hass, hass_client):
    """Test to ensure state and custom icons are returned."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set("light.kitchen", STATE_OFF, {"icon": "mdi:chemical-weapon"})
    hass.states.async_set(
        "light.kitchen", STATE_ON, {"brightness": 100, "icon": "mdi:security"}
    )
    hass.states.async_set(
        "light.kitchen", STATE_ON, {"brightness": 200, "icon": "mdi:security"}
    )
    hass.states.async_set(
        "light.kitchen", STATE_ON, {"brightness": 300, "icon": "mdi:security"}
    )
    hass.states.async_set(
        "light.kitchen", STATE_ON, {"brightness": 400, "icon": "mdi:security"}
    )
    hass.states.async_set("light.kitchen", STATE_OFF, {"icon": "mdi:chemical-weapon"})

    await _async_commit_and_wait(hass)

    client = await hass_client()
    response_json = await _async_fetch_logbook(client)

    assert len(response_json) == 3
    assert response_json[0]["domain"] == "homeassistant"
    assert response_json[1]["entity_id"] == "light.kitchen"
    assert response_json[1]["icon"] == "mdi:security"
    assert response_json[1]["state"] == STATE_ON
    assert response_json[2]["entity_id"] == "light.kitchen"
    assert response_json[2]["icon"] == "mdi:chemical-weapon"
    assert response_json[2]["state"] == STATE_OFF


async def test_exclude_events_domain(hass, hass_client):
    """Test if events are filtered if domain is excluded in config."""
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {CONF_EXCLUDE: {CONF_DOMAINS: ["switch", "alexa"]}},
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await _async_commit_and_wait(hass)

    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_exclude_events_domain_glob(hass, hass_client):
    """Test if events are filtered if domain or glob is excluded in config."""
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"
    entity_id3 = "sensor.excluded"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["switch", "alexa"],
                    CONF_ENTITY_GLOBS: "*.excluded",
                }
            },
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)
    hass.states.async_set(entity_id3, None)
    hass.states.async_set(entity_id3, 30)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_include_events_entity(hass, hass_client):
    """Test if events are filtered if entity is included in config."""
    entity_id = "sensor.bla"
    entity_id2 = "sensor.blu"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["homeassistant"],
                    CONF_ENTITIES: [entity_id2],
                }
            },
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_exclude_events_entity(hass, hass_client):
    """Test if events are filtered if entity is excluded in config."""
    entity_id = "sensor.bla"
    entity_id2 = "sensor.blu"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {CONF_EXCLUDE: {CONF_ENTITIES: [entity_id]}},
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)
    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_include_events_domain(hass, hass_client):
    """Test if events are filtered if domain is included in config."""
    assert await async_setup_component(hass, "alexa", {})
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"
    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                CONF_INCLUDE: {CONF_DOMAINS: ["homeassistant", "sensor", "alexa"]}
            },
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.bus.async_fire(
        EVENT_ALEXA_SMART_HOME,
        {"request": {"namespace": "Alexa.Discovery", "name": "Discover"}},
    )
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 3
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="Amazon Alexa", domain="alexa")
    _assert_entry(entries[2], name="blu", entity_id=entity_id2)


async def test_include_events_domain_glob(hass, hass_client):
    """Test if events are filtered if domain or glob is included in config."""
    assert await async_setup_component(hass, "alexa", {})
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"
    entity_id3 = "switch.included"
    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["homeassistant", "sensor", "alexa"],
                    CONF_ENTITY_GLOBS: ["*.included"],
                }
            },
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.bus.async_fire(
        EVENT_ALEXA_SMART_HOME,
        {"request": {"namespace": "Alexa.Discovery", "name": "Discover"}},
    )
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)
    hass.states.async_set(entity_id3, None)
    hass.states.async_set(entity_id3, 30)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 4
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="Amazon Alexa", domain="alexa")
    _assert_entry(entries[2], name="blu", entity_id=entity_id2)
    _assert_entry(entries[3], name="included", entity_id=entity_id3)


async def test_include_exclude_events(hass, hass_client):
    """Test if events are filtered if include and exclude is configured."""
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"
    entity_id3 = "sensor.bli"
    entity_id4 = "sensor.keep"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["sensor", "homeassistant"],
                    CONF_ENTITIES: ["switch.bla"],
                },
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["switch"],
                    CONF_ENTITIES: ["sensor.bli"],
                },
            },
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 10)
    hass.states.async_set(entity_id3, None)
    hass.states.async_set(entity_id3, 10)
    hass.states.async_set(entity_id, 20)
    hass.states.async_set(entity_id2, 20)
    hass.states.async_set(entity_id4, None)
    hass.states.async_set(entity_id4, 10)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 3
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)
    _assert_entry(entries[2], name="keep", entity_id=entity_id4)


async def test_include_exclude_events_with_glob_filters(hass, hass_client):
    """Test if events are filtered if include and exclude is configured."""
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"
    entity_id3 = "sensor.bli"
    entity_id4 = "light.included"
    entity_id5 = "switch.included"
    entity_id6 = "sensor.excluded"
    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["sensor", "homeassistant"],
                    CONF_ENTITIES: ["switch.bla"],
                    CONF_ENTITY_GLOBS: ["*.included"],
                },
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["switch"],
                    CONF_ENTITY_GLOBS: ["*.excluded"],
                    CONF_ENTITIES: ["sensor.bli"],
                },
            },
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 10)
    hass.states.async_set(entity_id3, None)
    hass.states.async_set(entity_id3, 10)
    hass.states.async_set(entity_id, 20)
    hass.states.async_set(entity_id2, 20)
    hass.states.async_set(entity_id4, None)
    hass.states.async_set(entity_id4, 30)
    hass.states.async_set(entity_id5, None)
    hass.states.async_set(entity_id5, 30)
    hass.states.async_set(entity_id6, None)
    hass.states.async_set(entity_id6, 30)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 3
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)
    _assert_entry(entries[2], name="included", entity_id=entity_id4)


async def test_empty_config(hass, hass_client):
    """Test we can handle an empty entity filter."""
    entity_id = "sensor.blu"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {},
        }
    )
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", config)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)

    await _async_commit_and_wait(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id)


async def _async_fetch_logbook(client):

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day) - timedelta(hours=24)

    # Test today entries without filters
    end_time = start + timedelta(hours=48)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    return await response.json()


async def _async_commit_and_wait(hass):
    await hass.async_block_till_done()
    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    await hass.async_block_till_done()


def _assert_entry(
    entry, when=None, name=None, message=None, domain=None, entity_id=None
):
    """Assert an entry is what is expected."""
    if when:
        assert when.isoformat() == entry["when"]

    if name:
        assert name == entry["name"]

    if message:
        assert message == entry["message"]

    if domain:
        assert domain == entry["domain"]

    if entity_id:
        assert entity_id == entry["entity_id"]


class MockLazyEventPartialState(ha.Event):
    """Minimal mock of a Lazy event."""

    @property
    def data_entity_id(self):
        """Lookup entity id."""
        return self.data.get(ATTR_ENTITY_ID)

    @property
    def data_domain(self):
        """Lookup domain."""
        return self.data.get(ATTR_DOMAIN)

    @property
    def time_fired_minute(self):
        """Minute the event was fired."""
        return self.time_fired.minute

    @property
    def context_user_id(self):
        """Context user id of event."""
        return self.context.user_id

    @property
    def context_id(self):
        """Context id of event."""
        return self.context.id

    @property
    def time_fired_isoformat(self):
        """Time event was fired in utc isoformat."""
        return process_timestamp_to_utc_isoformat(self.time_fired)
