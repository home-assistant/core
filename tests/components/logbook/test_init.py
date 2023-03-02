"""The tests for the logbook component."""
# pylint: disable=invalid-name
import asyncio
import collections
from collections.abc import Callable
from datetime import datetime, timedelta
from http import HTTPStatus
import json
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant.components import logbook, recorder
from homeassistant.components.alexa.smart_home import EVENT_ALEXA_SMART_HOME
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.components.logbook.models import LazyEventPartialState
from homeassistant.components.logbook.processor import EventProcessor
from homeassistant.components.logbook.queries.common import PSEUDO_EVENT_STATE_CHANGED
from homeassistant.components.recorder import Recorder
from homeassistant.components.script import EVENT_SCRIPT_STARTED
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    ATTR_SERVICE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGBOOK_ENTRY,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entityfilter import CONF_ENTITY_GLOBS
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import MockRow, mock_humanify

from tests.common import MockConfigEntry, async_capture_events, mock_platform
from tests.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator

EMPTY_CONFIG = logbook.CONFIG_SCHEMA({logbook.DOMAIN: {}})


@pytest.fixture
async def hass_(recorder_mock, hass):
    """Set up things to be run when tests are started."""
    assert await async_setup_component(hass, logbook.DOMAIN, EMPTY_CONFIG)
    return hass


@pytest.fixture
def set_utc(hass):
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


async def test_service_call_create_logbook_entry(hass_) -> None:
    """Test if service call create log book entry."""
    calls = async_capture_events(hass_, logbook.EVENT_LOGBOOK_ENTRY)

    await hass_.services.async_call(
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
    await hass_.services.async_call(
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
    await async_wait_recording_done(hass_)
    event_processor = EventProcessor(hass_, (EVENT_LOGBOOK_ENTRY,))

    events = list(
        event_processor.get_events(
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


async def test_service_call_create_logbook_entry_invalid_entity_id(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test if service call create log book entry with an invalid entity id."""
    await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()
    hass.bus.async_fire(
        logbook.EVENT_LOGBOOK_ENTRY,
        {
            logbook.ATTR_NAME: "Alarm",
            logbook.ATTR_MESSAGE: "is triggered",
            logbook.ATTR_DOMAIN: "switch",
            logbook.ATTR_ENTITY_ID: 1234,
        },
    )
    await async_wait_recording_done(hass)
    event_processor = EventProcessor(hass, (EVENT_LOGBOOK_ENTRY,))
    events = list(
        event_processor.get_events(
            dt_util.utcnow() - timedelta(hours=1),
            dt_util.utcnow() + timedelta(hours=1),
        )
    )
    assert len(events) == 1
    assert events[0][logbook.ATTR_DOMAIN] == "switch"
    assert events[0][logbook.ATTR_NAME] == "Alarm"
    assert events[0][logbook.ATTR_ENTITY_ID] == 1234
    assert events[0][logbook.ATTR_MESSAGE] == "is triggered"


async def test_service_call_create_log_book_entry_no_message(hass_) -> None:
    """Test if service call create log book entry without message."""
    calls = async_capture_events(hass_, logbook.EVENT_LOGBOOK_ENTRY)

    with pytest.raises(vol.Invalid):
        await hass_.services.async_call(logbook.DOMAIN, "log", {}, True)

    # Logbook entry service call results in firing an event.
    # Our service call will unblock when the event listeners have been
    # scheduled. This means that they may not have been processed yet.
    await hass_.async_block_till_done()

    assert len(calls) == 0


async def test_filter_sensor(
    hass_: ha.HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test numeric sensors are filtered."""

    registry = er.async_get(hass_)

    # Unregistered sensor without a unit of measurement - should be in logbook
    entity_id1 = "sensor.bla"
    attributes_1 = None
    # Unregistered sensor with a unit of measurement - should be excluded from logbook
    entity_id2 = "sensor.blu"
    attributes_2 = {ATTR_UNIT_OF_MEASUREMENT: "cats"}
    # Registered sensor with state class - should be excluded from logbook
    entity_id3 = registry.async_get_or_create(
        "sensor",
        "test",
        "unique_3",
        suggested_object_id="bli",
        capabilities={"state_class": SensorStateClass.MEASUREMENT},
    ).entity_id
    attributes_3 = None
    # Registered sensor without state class or unit - should be in logbook
    entity_id4 = registry.async_get_or_create(
        "sensor", "test", "unique_4", suggested_object_id="ble"
    ).entity_id
    attributes_4 = None

    hass_.states.async_set(entity_id1, None, attributes_1)  # Excluded
    hass_.states.async_set(entity_id1, 10, attributes_1)  # Included
    hass_.states.async_set(entity_id2, None, attributes_2)  # Excluded
    hass_.states.async_set(entity_id2, 10, attributes_2)  # Excluded
    hass_.states.async_set(entity_id3, None, attributes_3)  # Excluded
    hass_.states.async_set(entity_id3, 10, attributes_3)  # Excluded
    hass_.states.async_set(entity_id1, 20, attributes_1)  # Included
    hass_.states.async_set(entity_id2, 20, attributes_2)  # Excluded
    hass_.states.async_set(entity_id4, None, attributes_4)  # Excluded
    hass_.states.async_set(entity_id4, 10, attributes_4)  # Included

    await async_wait_recording_done(hass_)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 3
    _assert_entry(entries[0], name="bla", entity_id=entity_id1, state="10")
    _assert_entry(entries[1], name="bla", entity_id=entity_id1, state="20")
    _assert_entry(entries[2], name="ble", entity_id=entity_id4, state="10")


async def test_home_assistant_start_stop_not_grouped(hass_) -> None:
    """Test if HA start and stop events are no longer grouped."""
    await async_setup_component(hass_, "homeassistant", {})
    await hass_.async_block_till_done()
    entries = mock_humanify(
        hass_,
        (
            MockRow(EVENT_HOMEASSISTANT_STOP),
            MockRow(EVENT_HOMEASSISTANT_START),
        ),
    )

    assert len(entries) == 2
    assert_entry(entries[0], name="Home Assistant", message="stopped", domain=ha.DOMAIN)
    assert_entry(entries[1], name="Home Assistant", message="started", domain=ha.DOMAIN)


async def test_home_assistant_start(hass_) -> None:
    """Test if HA start is not filtered or converted into a restart."""
    await async_setup_component(hass_, "homeassistant", {})
    await hass_.async_block_till_done()
    entity_id = "switch.bla"
    pointA = dt_util.utcnow()

    entries = mock_humanify(
        hass_,
        (
            MockRow(EVENT_HOMEASSISTANT_START),
            create_state_changed_event(pointA, entity_id, 10).row,
        ),
    )

    assert len(entries) == 2
    assert_entry(entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN)
    assert_entry(entries[1], pointA, "bla", entity_id=entity_id)


def test_process_custom_logbook_entries(hass_) -> None:
    """Test if custom log book entries get added as an entry."""
    name = "Nice name"
    message = "has a custom entry"
    entity_id = "sun.sun"

    entries = mock_humanify(
        hass_,
        (
            MockRow(
                logbook.EVENT_LOGBOOK_ENTRY,
                {
                    logbook.ATTR_NAME: name,
                    logbook.ATTR_MESSAGE: message,
                    logbook.ATTR_ENTITY_ID: entity_id,
                },
            ),
        ),
    )

    assert len(entries) == 1
    assert_entry(entries[0], name=name, message=message, entity_id=entity_id)


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
            "event_type",
            "event_data",
            "time_fired",
            "time_fired_ts",
            "context_id",
            "context_user_id",
            "context_parent_id",
            "state",
            "entity_id",
            "domain",
            "attributes",
            "state_id",
            "old_state_id",
            "shared_attrs",
            "shared_data",
            "context_only",
        ],
    )

    row.event_type = PSEUDO_EVENT_STATE_CHANGED
    row.event_data = "{}"
    row.shared_data = "{}"
    row.attributes = attributes_json
    row.shared_attrs = attributes_json
    row.time_fired = event_time_fired
    row.time_fired_ts = dt_util.utc_to_timestamp(event_time_fired)
    row.state = new_state and new_state.get("state")
    row.entity_id = entity_id
    row.domain = entity_id and ha.split_entity_id(entity_id)[0]
    row.context_only = False
    row.context_id = None
    row.friendly_name = None
    row.icon = None
    row.old_format_icon = None
    row.context_user_id = None
    row.context_parent_id = None
    row.old_state_id = old_state and 1
    row.state_id = new_state and 1
    return LazyEventPartialState(row, {})


async def test_logbook_view(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)
    client = await hass_client()
    response = await client.get(f"/api/logbook/{dt_util.utcnow().isoformat()}")
    assert response.status == HTTPStatus.OK


async def test_logbook_view_invalid_start_date_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with an invalid date time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)
    client = await hass_client()
    response = await client.get("/api/logbook/INVALID")
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_logbook_view_invalid_end_date_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)
    client = await hass_client()
    response = await client.get(
        f"/api/logbook/{dt_util.utcnow().isoformat()}?end_time=INVALID"
    )
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_logbook_view_period_entity(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    set_utc,
) -> None:
    """Test the logbook view with period and entity."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "switch.second"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_second

    # Test today entries with filter by period
    response = await client.get(f"/api/logbook/{start_date.isoformat()}?period=1")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_second

    # Test today entries with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?entity=switch.test"
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test

    # Test entries for 3 days with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?period=3&entity=switch.test"
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test

    # Tomorrow time 00:00:00
    start = (dt_util.utcnow() + timedelta(days=1)).date()
    start_date = datetime(start.year, start.month, start.day)

    # Test tomorrow entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 0

    # Test tomorrow entries with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?entity=switch.test"
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 0

    # Test entries from tomorrow to 3 days ago with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?period=3&entity=switch.test"
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test


async def test_logbook_describe_event(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test teaching logbook about a new event."""

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
        await async_wait_recording_done(hass)

    client = await hass_client()
    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    results = await response.json()
    assert len(results) == 1
    event = results[0]
    assert event["name"] == "Test Name"
    assert event["message"] == "tested a message"
    assert event["domain"] == "test_domain"


async def test_exclude_described_event(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
            "entity_id": event.data[ATTR_ENTITY_ID],
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
        await async_wait_recording_done(hass)

    client = await hass_client()
    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    results = await response.json()
    assert len(results) == 1
    event = results[0]
    assert event["name"] == "Test Name"
    assert event["entity_id"] == "automation.included_rule"


async def test_logbook_view_end_time_entity(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with end_time and entity."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "switch.second"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_second

    # Test entries for 3 days with filter by entity_id
    end_time = start + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test"
    )
    assert response.status == HTTPStatus.OK
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
    assert response.status == HTTPStatus.OK
    response_json = await response.json()
    assert len(response_json) == 1
    assert response_json[0]["entity_id"] == entity_id_test


async def test_logbook_entity_filter_with_automations(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with end_time and entity with automations and scripts."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await async_recorder_block_till_done(hass)

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

    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
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
    assert response.status == HTTPStatus.OK
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
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()
    assert len(json_dict) == 1
    assert json_dict[0]["entity_id"] == entity_id_second


async def test_logbook_entity_no_longer_in_state_machine(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with an entity that hass been removed from the state machine."""
    await async_setup_component(hass, "logbook", {})
    await async_setup_component(hass, "automation", {})
    await async_setup_component(hass, "script", {})

    await async_wait_recording_done(hass)

    entity_id_test = "alarm_control_panel.area_001"
    hass.states.async_set(
        entity_id_test, STATE_OFF, {ATTR_FRIENDLY_NAME: "Alarm Control Panel"}
    )
    hass.states.async_set(
        entity_id_test, STATE_ON, {ATTR_FRIENDLY_NAME: "Alarm Control Panel"}
    )

    await async_wait_recording_done(hass)

    hass.states.async_remove(entity_id_test)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()
    assert json_dict[0]["name"] == "area 001"


async def test_filter_continuous_sensor_values(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    set_utc,
) -> None:
    """Test remove continuous sensor events from logbook."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "sensor.bla"
    hass.states.async_set(entity_id_second, STATE_OFF, {"unit_of_measurement": "foo"})
    hass.states.async_set(entity_id_second, STATE_ON, {"unit_of_measurement": "foo"})
    entity_id_third = "light.bla"
    hass.states.async_set(entity_id_third, STATE_OFF, {"unit_of_measurement": "foo"})
    hass.states.async_set(entity_id_third, STATE_ON, {"unit_of_measurement": "foo"})
    entity_id_proximity = "proximity.bla"
    hass.states.async_set(entity_id_proximity, STATE_OFF)
    hass.states.async_set(entity_id_proximity, STATE_ON)
    entity_id_counter = "counter.bla"
    hass.states.async_set(entity_id_counter, STATE_OFF)
    hass.states.async_set(entity_id_counter, STATE_ON)

    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()

    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id_test
    assert response_json[1]["entity_id"] == entity_id_third


async def test_exclude_new_entities(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    set_utc,
) -> None:
    """Test if events are excluded on first update."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    entity_id = "climate.bla"
    entity_id2 = "climate.blu"

    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set(entity_id2, STATE_ON)
    hass.states.async_set(entity_id2, STATE_OFF)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()

    assert len(response_json) == 2
    assert response_json[0]["entity_id"] == entity_id2
    assert response_json[1]["domain"] == "homeassistant"
    assert response_json[1]["message"] == "started"


async def test_exclude_removed_entities(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    set_utc,
) -> None:
    """Test if events are excluded on last update."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    entity_id = "climate.bla"
    entity_id2 = "climate.blu"

    hass.states.async_set(entity_id, STATE_ON)
    hass.states.async_set(entity_id, STATE_OFF)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set(entity_id2, STATE_ON)
    hass.states.async_set(entity_id2, STATE_OFF)

    hass.states.async_remove(entity_id)
    hass.states.async_remove(entity_id2)

    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()

    assert len(response_json) == 3
    assert response_json[0]["entity_id"] == entity_id
    assert response_json[1]["domain"] == "homeassistant"
    assert response_json[1]["message"] == "started"
    assert response_json[2]["entity_id"] == entity_id2


async def test_exclude_attribute_changes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    set_utc,
) -> None:
    """Test if events of attribute changes are filtered."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set("light.kitchen", STATE_OFF)
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 100})
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 200})
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 300})
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 400})
    hass.states.async_set("light.kitchen", STATE_OFF)

    await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == HTTPStatus.OK
    response_json = await response.json()

    assert len(response_json) == 3
    assert response_json[0]["domain"] == "homeassistant"
    assert response_json[1]["entity_id"] == "light.kitchen"
    assert response_json[2]["entity_id"] == "light.kitchen"


async def test_logbook_entity_context_id(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with end_time and entity with automations and scripts."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await async_recorder_block_till_done(hass)

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
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
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


async def test_logbook_context_id_automation_script_started_manually(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook populates context_ids for scripts and automations started manually."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await async_recorder_block_till_done(hass)

    # An Automation
    automation_entity_id_test = "automation.alarm"
    automation_context = ha.Context(
        id="fc5bd62de45711eaaeb351041eec8dd9",
        user_id="f400facee45711eaa9308bfd3d19e474",
    )
    hass.bus.async_fire(
        EVENT_AUTOMATION_TRIGGERED,
        {ATTR_NAME: "Mock automation", ATTR_ENTITY_ID: automation_entity_id_test},
        context=automation_context,
    )
    script_context = ha.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script", ATTR_ENTITY_ID: "script.mock_script"},
        context=script_context,
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    script_2_context = ha.Context(
        id="1234",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    hass.bus.async_fire(
        EVENT_SCRIPT_STARTED,
        {ATTR_NAME: "Mock script"},
        context=script_2_context,
    )
    hass.states.async_set("switch.new", STATE_ON, context=script_2_context)
    hass.states.async_set("switch.new", STATE_OFF, context=script_2_context)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert json_dict[0]["entity_id"] == "automation.alarm"
    assert "context_entity_id" not in json_dict[0]
    assert json_dict[0]["context_user_id"] == "f400facee45711eaa9308bfd3d19e474"
    assert json_dict[0]["context_id"] == "fc5bd62de45711eaaeb351041eec8dd9"

    assert json_dict[1]["entity_id"] == "script.mock_script"
    assert "context_entity_id" not in json_dict[1]
    assert json_dict[1]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"
    assert json_dict[1]["context_id"] == "ac5bd62de45711eaaeb351041eec8dd9"

    assert json_dict[2]["domain"] == "homeassistant"

    assert json_dict[3]["entity_id"] is None
    assert json_dict[3]["name"] == "Mock script"
    assert "context_entity_id" not in json_dict[1]
    assert json_dict[3]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"
    assert json_dict[3]["context_id"] == "1234"

    assert json_dict[4]["entity_id"] == "switch.new"
    assert json_dict[4]["state"] == "off"
    assert "context_entity_id" not in json_dict[1]
    assert json_dict[4]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"
    assert json_dict[4]["context_event_type"] == "script_started"
    assert json_dict[4]["context_domain"] == "script"


async def test_logbook_entity_context_parent_id(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view links events via context parent_id."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await async_recorder_block_till_done(hass)

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
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
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


async def test_logbook_context_from_template(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with end_time and entity with automations and scripts."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )

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
    await async_recorder_block_till_done(hass)
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
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == HTTPStatus.OK
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


async def test_logbook_(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with a single entity and ."""
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
    await async_recorder_block_till_done(hass)
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
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test_state"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 2

    assert json_dict[0]["entity_id"] == "switch.test_state"

    assert json_dict[1]["entity_id"] == "switch.test_state"
    assert json_dict[1]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_logbook_many_entities_multiple_calls(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with a many entities called multiple times."""
    await async_setup_component(hass, "logbook", {})
    await async_setup_component(hass, "automation", {})

    await async_recorder_block_till_done(hass)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    for automation_id in range(5):
        hass.bus.async_fire(
            EVENT_AUTOMATION_TRIGGERED,
            {
                ATTR_NAME: f"Mock automation {automation_id}",
                ATTR_ENTITY_ID: f"automation.mock_{automation_id}_automation",
            },
        )
    await async_wait_recording_done(hass)
    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)
    end_time = start + timedelta(hours=24)

    for automation_id in range(5):
        # Test today entries with filter by end_time
        response = await client.get(
            f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=automation.mock_{automation_id}_automation"
        )
        assert response.status == HTTPStatus.OK
        json_dict = await response.json()

        assert len(json_dict) == 1
        assert (
            json_dict[0]["entity_id"] == f"automation.mock_{automation_id}_automation"
        )

    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=automation.mock_0_automation,automation.mock_1_automation,automation.mock_2_automation"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 3
    assert json_dict[0]["entity_id"] == "automation.mock_0_automation"
    assert json_dict[1]["entity_id"] == "automation.mock_1_automation"
    assert json_dict[2]["entity_id"] == "automation.mock_2_automation"

    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=automation.mock_4_automation,automation.mock_2_automation,automation.mock_0_automation,automation.mock_1_automation"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 4
    assert json_dict[0]["entity_id"] == "automation.mock_0_automation"
    assert json_dict[1]["entity_id"] == "automation.mock_1_automation"
    assert json_dict[2]["entity_id"] == "automation.mock_2_automation"
    assert json_dict[3]["entity_id"] == "automation.mock_4_automation"

    response = await client.get(
        f"/api/logbook/{end_time.isoformat()}?end_time={end_time}&entity=automation.mock_4_automation,automation.mock_2_automation,automation.mock_0_automation,automation.mock_1_automation"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()
    assert len(json_dict) == 0


async def test_custom_log_entry_discoverable_via_(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test if a custom log entry is later discoverable via ."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    logbook.async_log_entry(
        hass,
        "Alarm",
        "is triggered",
        "switch",
        "switch.test_switch",
    )
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time.isoformat()}&entity=switch.test_switch"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 1

    assert json_dict[0]["name"] == "Alarm"
    assert json_dict[0]["message"] == "is triggered"
    assert json_dict[0]["entity_id"] == "switch.test_switch"


async def test_logbook_multiple_entities(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with a multiple entities."""
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
    await async_recorder_block_till_done(hass)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Entity added (should not be logged)
    hass.states.async_set("switch.test_state", STATE_ON)
    hass.states.async_set("light.test_state", STATE_ON)
    hass.states.async_set("binary_sensor.test_state", STATE_ON)

    await hass.async_block_till_done()

    # First state change (should be logged)
    hass.states.async_set("switch.test_state", STATE_OFF)
    hass.states.async_set("light.test_state", STATE_OFF)
    hass.states.async_set("binary_sensor.test_state", STATE_OFF)

    await hass.async_block_till_done()

    switch_turn_off_context = ha.Context(
        id="9c5bd62de45711eaaeb351041eec8dd9",
        user_id="9400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set(
        "switch.test_state", STATE_ON, context=switch_turn_off_context
    )
    hass.states.async_set("light.test_state", STATE_ON, context=switch_turn_off_context)
    hass.states.async_set(
        "binary_sensor.test_state", STATE_ON, context=switch_turn_off_context
    )
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test_state,light.test_state"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 4

    assert json_dict[0]["entity_id"] == "switch.test_state"

    assert json_dict[1]["entity_id"] == "light.test_state"

    assert json_dict[2]["entity_id"] == "switch.test_state"
    assert json_dict[2]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == "light.test_state"
    assert json_dict[3]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=binary_sensor.test_state,light.test_state"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 4

    assert json_dict[0]["entity_id"] == "light.test_state"

    assert json_dict[1]["entity_id"] == "binary_sensor.test_state"

    assert json_dict[2]["entity_id"] == "light.test_state"
    assert json_dict[2]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == "binary_sensor.test_state"
    assert json_dict[3]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=light.test_state,binary_sensor.test_state"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert len(json_dict) == 4

    assert json_dict[0]["entity_id"] == "light.test_state"

    assert json_dict[1]["entity_id"] == "binary_sensor.test_state"

    assert json_dict[2]["entity_id"] == "light.test_state"
    assert json_dict[2]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == "binary_sensor.test_state"
    assert json_dict[3]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_logbook_invalid_entity(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with requesting an invalid entity."""
    await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()
    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=invalid"
    )
    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_icon_and_state(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test to ensure state and custom icons are returned."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )

    await async_recorder_block_till_done(hass)

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

    await async_wait_recording_done(hass)

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


async def test_fire_logbook_entries(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test many logbook entry calls."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    for _ in range(10):
        hass.bus.async_fire(
            logbook.EVENT_LOGBOOK_ENTRY,
            {
                logbook.ATTR_NAME: "Alarm",
                logbook.ATTR_MESSAGE: "is triggered",
                logbook.ATTR_DOMAIN: "switch",
                logbook.ATTR_ENTITY_ID: "sensor.xyz",
            },
        )
        hass.bus.async_fire(
            logbook.EVENT_LOGBOOK_ENTRY,
            {},
        )
    hass.bus.async_fire(
        logbook.EVENT_LOGBOOK_ENTRY,
        {
            logbook.ATTR_NAME: "Alarm",
            logbook.ATTR_MESSAGE: "is triggered",
            logbook.ATTR_DOMAIN: "switch",
        },
    )
    await async_wait_recording_done(hass)

    client = await hass_client()
    response_json = await _async_fetch_logbook(client)

    # The empty events should be skipped
    assert len(response_json) == 11


async def test_exclude_events_domain(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test if events are filtered if domain is excluded in config."""
    entity_id = "switch.bla"
    entity_id2 = "sensor.blu"

    await async_setup_component(hass, "homeassistant", {})
    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {CONF_EXCLUDE: {CONF_DOMAINS: ["switch", "alexa"]}},
        }
    )
    await async_setup_component(hass, "logbook", config)
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await async_wait_recording_done(hass)

    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_exclude_events_domain_glob(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)
    hass.states.async_set(entity_id3, None)
    hass.states.async_set(entity_id3, 30)

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_include_events_entity(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_exclude_events_entity(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test if events are filtered if entity is excluded in config."""
    entity_id = "sensor.bla"
    entity_id2 = "sensor.blu"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {CONF_EXCLUDE: {CONF_ENTITIES: [entity_id]}},
        }
    )
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)
    hass.states.async_set(entity_id2, None)
    hass.states.async_set(entity_id2, 20)

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)
    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id2)


async def test_include_events_domain(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

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

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 3
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="Amazon Alexa", domain="alexa")
    _assert_entry(entries[2], name="blu", entity_id=entity_id2)


async def test_include_events_domain_glob(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(
        logbook.EVENT_LOGBOOK_ENTRY,
        {
            logbook.ATTR_NAME: "Alarm",
            logbook.ATTR_MESSAGE: "is triggered",
            logbook.ATTR_ENTITY_ID: "switch.any",
        },
    )
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

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 4
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="Amazon Alexa", domain="alexa")
    _assert_entry(entries[2], name="blu", entity_id=entity_id2)
    _assert_entry(entries[3], name="included", entity_id=entity_id3)


async def test_include_exclude_events_no_globs(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

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

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 6
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="bla", entity_id=entity_id, state="10")
    _assert_entry(entries[2], name="blu", entity_id=entity_id2, state="10")
    _assert_entry(entries[3], name="bla", entity_id=entity_id, state="20")
    _assert_entry(entries[4], name="blu", entity_id=entity_id2, state="20")
    _assert_entry(entries[5], name="keep", entity_id=entity_id4, state="10")


async def test_include_exclude_events_with_glob_filters(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

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

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 7
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="bla", entity_id=entity_id, state="10")
    _assert_entry(entries[2], name="blu", entity_id=entity_id2, state="10")
    _assert_entry(entries[3], name="bla", entity_id=entity_id, state="20")
    _assert_entry(entries[4], name="blu", entity_id=entity_id2, state="20")
    _assert_entry(entries[5], name="included", entity_id=entity_id4, state="30")
    _assert_entry(entries[6], name="included", entity_id=entity_id5, state="30")


async def test_empty_config(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test we can handle an empty entity filter."""
    entity_id = "sensor.blu"

    config = logbook.CONFIG_SCHEMA(
        {
            ha.DOMAIN: {},
            logbook.DOMAIN: {},
        }
    )
    await asyncio.gather(
        async_setup_component(hass, "homeassistant", {}),
        async_setup_component(hass, "logbook", config),
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, 10)

    await async_wait_recording_done(hass)
    client = await hass_client()
    entries = await _async_fetch_logbook(client)

    assert len(entries) == 2
    _assert_entry(
        entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
    )
    _assert_entry(entries[1], name="blu", entity_id=entity_id)


async def test_context_filter(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test we can filter by context."""
    assert await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    entity_id = "switch.blu"
    context = ha.Context()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    hass.states.async_set(entity_id, None)
    hass.states.async_set(entity_id, "on", context=context)
    hass.states.async_set(entity_id, "off")
    hass.states.async_set(entity_id, "unknown", context=context)

    await async_wait_recording_done(hass)
    client = await hass_client()

    # Test results
    entries = await _async_fetch_logbook(client, {"context_id": context.id})

    assert len(entries) == 2
    _assert_entry(entries[0], entity_id=entity_id, state="on")
    _assert_entry(entries[1], entity_id=entity_id, state="unknown")

    # Test we can't combine context filter with entity_id filter
    response = await client.get(
        "/api/logbook", params={"context_id": context.id, "entity": entity_id}
    )
    assert response.status == HTTPStatus.BAD_REQUEST


async def _async_fetch_logbook(client, params=None):
    if params is None:
        params = {}

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day) - timedelta(hours=24)

    if "end_time" not in params:
        params["end_time"] = str(start + timedelta(hours=48))

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}", params=params)
    assert response.status == HTTPStatus.OK
    return await response.json()


def _assert_entry(
    entry, when=None, name=None, message=None, domain=None, entity_id=None, state=None
):
    """Assert an entry is what is expected."""
    if when is not None:
        assert when.isoformat() == entry["when"]

    if name is not None:
        assert name == entry["name"]

    if message is not None:
        assert message == entry["message"]

    if domain is not None:
        assert domain == entry["domain"]

    if entity_id is not None:
        assert entity_id == entry["entity_id"]

    if state is not None:
        assert state == entry["state"]


async def test_get_events(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook get_events."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    hass.states.async_set("light.kitchen", STATE_OFF)
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 300})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 400})
    await hass.async_block_till_done()
    context = ha.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )

    hass.states.async_set("light.kitchen", STATE_OFF, context=context)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2
    assert response["result"] == []

    await client.send_json(
        {
            "id": 3,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3

    results = response["result"]
    assert results[0]["entity_id"] == "light.kitchen"
    assert results[0]["state"] == "on"
    assert results[1]["entity_id"] == "light.kitchen"
    assert results[1]["state"] == "off"

    await client.send_json(
        {
            "id": 4,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 4

    results = response["result"]
    assert len(results) == 3
    assert results[0]["message"] == "started"
    assert results[1]["entity_id"] == "light.kitchen"
    assert results[1]["state"] == "on"
    assert isinstance(results[1]["when"], float)
    assert results[2]["entity_id"] == "light.kitchen"
    assert results[2]["state"] == "off"
    assert isinstance(results[2]["when"], float)

    await client.send_json(
        {
            "id": 5,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "context_id": "ac5bd62de45711eaaeb351041eec8dd9",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 5

    results = response["result"]
    assert len(results) == 1
    assert results[0]["entity_id"] == "light.kitchen"
    assert results[0]["state"] == "off"
    assert isinstance(results[0]["when"], float)


async def test_get_events_future_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events with a future start time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)
    future = dt_util.utcnow() + timedelta(hours=10)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": future.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1

    results = response["result"]
    assert isinstance(results, list)
    assert len(results) == 0


async def test_get_events_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events bad start time."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


async def test_get_events_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events bad end time."""
    now = dt_util.utcnow()
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "end_time": "dogs",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_get_events_invalid_filters(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_events invalid filters."""
    await async_setup_component(hass, "logbook", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "entity_ids": [],
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "device_ids": [],
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_get_events_with_device_ids(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test logbook get_events for device ids."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )

    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="device name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )

    class MockLogbookPlatform:
        """Mock a logbook platform."""

        @ha.callback
        def async_describe_events(
            hass: HomeAssistant,
            async_describe_event: Callable[
                [str, str, Callable[[Event], dict[str, str]]], None
            ],
        ) -> None:
            """Describe logbook events."""

            @ha.callback
            def async_describe_test_event(event: Event) -> dict[str, str]:
                """Describe mock logbook event."""
                return {
                    "name": "device name",
                    "message": "is on fire",
                }

            async_describe_event("test", "mock_event", async_describe_test_event)

    await logbook._process_logbook_platform(hass, "test", MockLogbookPlatform)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.bus.async_fire("mock_event", {"device_id": device.id})

    hass.states.async_set("light.kitchen", STATE_OFF)
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 100})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 200})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 300})
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", STATE_ON, {"brightness": 400})
    await hass.async_block_till_done()
    context = ha.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )

    hass.states.async_set("light.kitchen", STATE_OFF, context=context)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "device_ids": [device.id],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1

    results = response["result"]
    assert len(results) == 1
    assert results[0]["name"] == "device name"
    assert results[0]["message"] == "is on fire"
    assert isinstance(results[0]["when"], float)

    await client.send_json(
        {
            "id": 2,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
            "entity_ids": ["light.kitchen"],
            "device_ids": [device.id],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2

    results = response["result"]
    assert results[0]["domain"] == "test"
    assert results[0]["message"] == "is on fire"
    assert results[0]["name"] == "device name"
    assert results[1]["entity_id"] == "light.kitchen"
    assert results[1]["state"] == "on"
    assert results[2]["entity_id"] == "light.kitchen"
    assert results[2]["state"] == "off"

    await client.send_json(
        {
            "id": 3,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3

    results = response["result"]
    assert len(results) == 4
    assert results[0]["message"] == "started"
    assert results[1]["name"] == "device name"
    assert results[1]["message"] == "is on fire"
    assert isinstance(results[1]["when"], float)
    assert results[2]["entity_id"] == "light.kitchen"
    assert results[2]["state"] == "on"
    assert isinstance(results[2]["when"], float)
    assert results[3]["entity_id"] == "light.kitchen"
    assert results[3]["state"] == "off"
    assert isinstance(results[3]["when"], float)


async def test_logbook_select_entities_context_id(
    recorder_mock: Recorder, hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the logbook view with end_time and entity with automations and scripts."""
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook", "automation", "script")
        ]
    )

    await async_recorder_block_till_done(hass)

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
    entity_id_third = "alarm_control_panel.area_003"

    logbook.async_log_entry(
        hass,
        "mock_name",
        "mock_message",
        "alarm_control_panel",
        entity_id_third,
        context,
    )
    await hass.async_block_till_done()

    logbook.async_log_entry(
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
    await async_wait_recording_done(hass)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity={entity_id_test},{entity_id_second},{entity_id_third},light.switch"
    )
    assert response.status == HTTPStatus.OK
    json_dict = await response.json()

    assert json_dict[0]["entity_id"] == entity_id_test
    assert json_dict[0]["context_event_type"] == "automation_triggered"
    assert json_dict[0]["context_entity_id"] == "automation.alarm"
    assert json_dict[0]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[0]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[1]["entity_id"] == entity_id_second
    assert json_dict[1]["context_event_type"] == "automation_triggered"
    assert json_dict[1]["context_entity_id"] == "automation.alarm"
    assert json_dict[1]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[1]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[2]["entity_id"] == "alarm_control_panel.area_003"
    assert json_dict[2]["context_event_type"] == "automation_triggered"
    assert json_dict[2]["context_entity_id"] == "automation.alarm"
    assert json_dict[2]["domain"] == "alarm_control_panel"
    assert json_dict[2]["context_entity_id_name"] == "Alarm Automation"
    assert json_dict[2]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"

    assert json_dict[3]["entity_id"] == "light.switch"
    assert json_dict[3]["context_event_type"] == "call_service"
    assert json_dict[3]["context_domain"] == "light"
    assert json_dict[3]["context_service"] == "turn_off"
    assert json_dict[3]["context_user_id"] == "9400facee45711eaa9308bfd3d19e474"


async def test_get_events_with_context_state(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test logbook get_events with a context state."""
    now = dt_util.utcnow()
    await asyncio.gather(
        *[
            async_setup_component(hass, comp, {})
            for comp in ("homeassistant", "logbook")
        ]
    )
    await async_recorder_block_till_done(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    hass.states.async_set("binary_sensor.is_light", STATE_ON)
    hass.states.async_set("light.kitchen1", STATE_OFF)
    hass.states.async_set("light.kitchen2", STATE_OFF)

    context = ha.Context(
        id="ac5bd62de45711eaaeb351041eec8dd9",
        user_id="b400facee45711eaa9308bfd3d19e474",
    )
    hass.states.async_set("binary_sensor.is_light", STATE_OFF, context=context)
    await hass.async_block_till_done()
    hass.states.async_set(
        "light.kitchen1", STATE_ON, {"brightness": 100}, context=context
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "light.kitchen2", STATE_ON, {"brightness": 200}, context=context
    )
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": now.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    results = response["result"]
    assert results[1]["entity_id"] == "binary_sensor.is_light"
    assert results[1]["state"] == "off"
    assert "context_state" not in results[1]
    assert results[2]["entity_id"] == "light.kitchen1"
    assert results[2]["state"] == "on"
    assert results[2]["context_entity_id"] == "binary_sensor.is_light"
    assert results[2]["context_state"] == "off"
    assert results[2]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"
    assert "context_event_type" not in results[2]
    assert results[3]["entity_id"] == "light.kitchen2"
    assert results[3]["state"] == "on"
    assert results[3]["context_entity_id"] == "binary_sensor.is_light"
    assert results[3]["context_state"] == "off"
    assert results[3]["context_user_id"] == "b400facee45711eaa9308bfd3d19e474"
    assert "context_event_type" not in results[3]


async def test_logbook_with_empty_config(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test we handle a empty configuration."""
    assert await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {},
            recorder.DOMAIN: {},
        },
    )
    await hass.async_block_till_done()


async def test_logbook_with_non_iterable_entity_filter(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test we handle a non-iterable entity filter."""
    assert await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_ENTITIES: ["light.additional_excluded"],
                }
            },
            recorder.DOMAIN: {
                CONF_EXCLUDE: {
                    CONF_ENTITIES: None,
                    CONF_DOMAINS: None,
                    CONF_ENTITY_GLOBS: None,
                }
            },
        },
    )
    await hass.async_block_till_done()
