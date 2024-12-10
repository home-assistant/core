"""The tests for the Recorder component."""

from datetime import datetime, timedelta
from unittest.mock import PropertyMock

import pytest

from homeassistant.components.recorder.const import SupportedDialect
from homeassistant.components.recorder.db_schema import (
    EventData,
    Events,
    StateAttributes,
    States,
)
from homeassistant.components.recorder.models import (
    LazyState,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.const import EVENT_STATE_CHANGED
import homeassistant.core as ha
from homeassistant.exceptions import InvalidEntityFormatError
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads


def test_from_event_to_db_event() -> None:
    """Test converting event to db event."""
    event = ha.Event(
        "test_event",
        {"some_data": 15},
        context=ha.Context(
            id="01EYQZJXZ5Z1Z1Z1Z1Z1Z1Z1Z1",
            parent_id="01EYQZJXZ5Z1Z1Z1Z1Z1Z1Z1Z1",
            user_id="12345678901234567890123456789012",
        ),
    )
    db_event = Events.from_event(event)
    dialect = SupportedDialect.MYSQL
    db_event.event_data = EventData.shared_data_bytes_from_event(event, dialect)
    db_event.event_type = event.event_type
    assert event.as_dict() == db_event.to_native().as_dict()


def test_from_event_to_db_event_with_null() -> None:
    """Test converting event to EventData with a null with PostgreSQL."""
    event = ha.Event(
        "test_event",
        {"some_data": "withnull\0terminator"},
    )
    dialect = SupportedDialect.POSTGRESQL
    event_data = EventData.shared_data_bytes_from_event(event, dialect)
    decoded = json_loads(event_data)
    assert decoded["some_data"] == "withnull"


def test_from_event_to_db_state() -> None:
    """Test converting event to db state."""
    state = ha.State(
        "sensor.temperature",
        "18",
        context=ha.Context(
            id="01EYQZJXZ5Z1Z1Z1Z1Z1Z1Z1Z1",
            parent_id="01EYQZJXZ5Z1Z1Z1Z1Z1Z1Z1Z1",
            user_id="12345678901234567890123456789012",
        ),
    )
    event = ha.Event(
        EVENT_STATE_CHANGED,
        {"entity_id": "sensor.temperature", "old_state": None, "new_state": state},
        context=state.context,
    )
    assert state.as_dict() == States.from_event(event).to_native().as_dict()


def test_from_event_to_db_state_attributes() -> None:
    """Test converting event to db state attributes."""
    attrs = {"this_attr": True}
    state = ha.State("sensor.temperature", "18", attrs)
    event = ha.Event(
        EVENT_STATE_CHANGED,
        {"entity_id": "sensor.temperature", "old_state": None, "new_state": state},
        context=state.context,
    )
    db_attrs = StateAttributes()
    dialect = SupportedDialect.MYSQL

    db_attrs.shared_attrs = StateAttributes.shared_attrs_bytes_from_event(
        event, dialect
    )
    assert db_attrs.to_native() == attrs


def test_from_event_to_db_state_attributes_with_null() -> None:
    """Test converting a state to StateAttributes with a null with PostgreSQL."""
    attrs = {"this_attr": "withnull\0terminator"}
    state = ha.State("sensor.temperature", "18", attrs)
    event = ha.Event(
        EVENT_STATE_CHANGED,
        {"entity_id": "sensor.temperature", "old_state": None, "new_state": state},
        context=state.context,
    )
    dialect = SupportedDialect.POSTGRESQL
    shared_attrs = StateAttributes.shared_attrs_bytes_from_event(event, dialect)
    decoded = json_loads(shared_attrs)
    assert decoded["this_attr"] == "withnull"


def test_repr() -> None:
    """Test converting event to db state repr."""
    attrs = {"this_attr": True}
    fixed_time = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC, microsecond=432432)
    state = ha.State(
        "sensor.temperature",
        "18",
        attrs,
        last_changed=fixed_time,
        last_updated=fixed_time,
    )
    event = ha.Event(
        EVENT_STATE_CHANGED,
        {"entity_id": "sensor.temperature", "old_state": None, "new_state": state},
        context=state.context,
        time_fired_timestamp=fixed_time.timestamp(),
    )
    assert "2016-07-09 11:00:00+00:00" in repr(States.from_event(event))
    assert "2016-07-09 11:00:00+00:00" in repr(Events.from_event(event))


def test_states_repr_without_timestamp() -> None:
    """Test repr for a state without last_updated_ts."""
    fixed_time = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC, microsecond=432432)
    states = States(
        entity_id="sensor.temp",
        attributes=None,
        context_id=None,
        context_user_id=None,
        context_parent_id=None,
        origin_idx=None,
        last_updated=fixed_time,
        last_changed=fixed_time,
        last_updated_ts=None,
        last_changed_ts=None,
    )
    assert "2016-07-09 11:00:00+00:00" in repr(states)


def test_events_repr_without_timestamp() -> None:
    """Test repr for an event without time_fired_ts."""
    fixed_time = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC, microsecond=432432)
    events = Events(
        event_type="any",
        event_data=None,
        origin_idx=None,
        time_fired=fixed_time,
        time_fired_ts=None,
        context_id=None,
        context_user_id=None,
        context_parent_id=None,
    )
    assert "2016-07-09 11:00:00+00:00" in repr(events)


def test_handling_broken_json_state_attributes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we handle broken json in state attributes."""
    state_attributes = StateAttributes(
        attributes_id=444, hash=1234, shared_attrs="{NOT_PARSE}"
    )
    assert state_attributes.to_native() == {}
    assert "Error converting row to state attributes" in caplog.text


def test_from_event_to_delete_state() -> None:
    """Test converting deleting state event to db state."""
    event = ha.Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.temperature",
            "old_state": ha.State("sensor.temperature", "18"),
            "new_state": None,
        },
    )
    db_state = States.from_event(event)

    assert db_state.entity_id == "sensor.temperature"
    assert db_state.state == ""
    assert db_state.last_changed_ts is None
    assert db_state.last_updated_ts == pytest.approx(event.time_fired.timestamp())


def test_states_from_native_invalid_entity_id() -> None:
    """Test loading a state from an invalid entity ID."""
    state = States()
    state.entity_id = "test.invalid__id"
    state.attributes = "{}"
    with pytest.raises(InvalidEntityFormatError):
        state = state.to_native()

    state = state.to_native(validate_entity_id=False)
    assert state.entity_id == "test.invalid__id"


async def test_process_timestamp() -> None:
    """Test processing time stamp to UTC."""
    datetime_with_tzinfo = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC)
    datetime_without_tzinfo = datetime(2016, 7, 9, 11, 0, 0)
    est = dt_util.get_time_zone("US/Eastern")
    datetime_est_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=est)
    nst = dt_util.get_time_zone("Canada/Newfoundland")
    datetime_nst_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=nst)
    hst = dt_util.get_time_zone("US/Hawaii")
    datetime_hst_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=hst)

    assert process_timestamp(datetime_with_tzinfo) == datetime(
        2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC
    )
    assert process_timestamp(datetime_without_tzinfo) == datetime(
        2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC
    )
    assert process_timestamp(datetime_est_timezone) == datetime(
        2016, 7, 9, 15, 0, tzinfo=dt_util.UTC
    )
    assert process_timestamp(datetime_nst_timezone) == datetime(
        2016, 7, 9, 13, 30, tzinfo=dt_util.UTC
    )
    assert process_timestamp(datetime_hst_timezone) == datetime(
        2016, 7, 9, 21, 0, tzinfo=dt_util.UTC
    )
    assert process_timestamp(None) is None


async def test_process_timestamp_to_utc_isoformat() -> None:
    """Test processing time stamp to UTC isoformat."""
    datetime_with_tzinfo = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt_util.UTC)
    datetime_without_tzinfo = datetime(2016, 7, 9, 11, 0, 0)
    est = dt_util.get_time_zone("US/Eastern")
    datetime_est_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=est)
    est = dt_util.get_time_zone("US/Eastern")
    datetime_est_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=est)
    nst = dt_util.get_time_zone("Canada/Newfoundland")
    datetime_nst_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=nst)
    hst = dt_util.get_time_zone("US/Hawaii")
    datetime_hst_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=hst)

    assert (
        process_timestamp_to_utc_isoformat(datetime_with_tzinfo)
        == "2016-07-09T11:00:00+00:00"
    )
    assert (
        process_timestamp_to_utc_isoformat(datetime_without_tzinfo)
        == "2016-07-09T11:00:00+00:00"
    )
    assert (
        process_timestamp_to_utc_isoformat(datetime_est_timezone)
        == "2016-07-09T15:00:00+00:00"
    )
    assert (
        process_timestamp_to_utc_isoformat(datetime_nst_timezone)
        == "2016-07-09T13:30:00+00:00"
    )
    assert (
        process_timestamp_to_utc_isoformat(datetime_hst_timezone)
        == "2016-07-09T21:00:00+00:00"
    )
    assert process_timestamp_to_utc_isoformat(None) is None


async def test_event_to_db_model() -> None:
    """Test we can round trip Event conversion."""
    event = ha.Event(
        "state_changed",
        {"some": "attr"},
        ha.EventOrigin.local,
        dt_util.utcnow().timestamp(),
    )
    db_event = Events.from_event(event)
    dialect = SupportedDialect.MYSQL
    db_event.event_data = EventData.shared_data_bytes_from_event(event, dialect)
    db_event.event_type = event.event_type
    native = db_event.to_native()
    assert native.as_dict() == event.as_dict()

    native = Events.from_event(event).to_native()
    native.data = (
        event.data
    )  # data is not set by from_event as its in the event_data table
    native.event_type = event.event_type
    assert native.as_dict() == event.as_dict()


async def test_lazy_state_handles_include_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState class handles invalid json."""
    row = PropertyMock(
        entity_id="sensor.invalid",
        shared_attrs="{INVALID_JSON}",
    )
    assert LazyState(row, {}, None, row.entity_id, "", 1, False).attributes == {}
    assert "Error converting row to state attributes" in caplog.text


async def test_lazy_state_can_decode_attributes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState prefers can decode attributes."""
    row = PropertyMock(
        entity_id="sensor.invalid",
        attributes='{"shared":true}',
    )
    assert LazyState(row, {}, None, row.entity_id, "", 1, False).attributes == {
        "shared": True
    }


async def test_lazy_state_handles_different_last_updated_and_last_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles different last_updated and last_changed."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        attributes='{"shared":true}',
        last_updated_ts=now.timestamp(),
        last_reported_ts=now.timestamp(),
        last_changed_ts=(now - timedelta(seconds=60)).timestamp(),
    )
    lstate = LazyState(
        row, {}, None, row.entity_id, row.state, row.last_updated_ts, False
    )
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.last_reported.timestamp() == row.last_updated_ts
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_changed_timestamp == row.last_changed_ts
    assert lstate.last_updated_timestamp == row.last_updated_ts
    assert lstate.last_reported_timestamp == row.last_updated_ts


async def test_lazy_state_handles_same_last_updated_and_last_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles same last_updated and last_changed."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        attributes='{"shared":true}',
        last_updated_ts=now.timestamp(),
        last_changed_ts=now.timestamp(),
        last_reported_ts=None,
    )
    lstate = LazyState(
        row, {}, None, row.entity_id, row.state, row.last_updated_ts, False
    )
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.last_reported.timestamp() == row.last_updated_ts
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_changed_timestamp == row.last_changed_ts
    assert lstate.last_updated_timestamp == row.last_updated_ts
    assert lstate.last_reported_timestamp == row.last_updated_ts


async def test_lazy_state_handles_different_last_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles last_reported different from last_updated."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        attributes='{"shared":true}',
        last_updated_ts=(now - timedelta(seconds=60)).timestamp(),
        last_reported_ts=now.timestamp(),
        last_changed_ts=(now - timedelta(seconds=60)).timestamp(),
    )
    lstate = LazyState(
        row, {}, None, row.entity_id, row.state, row.last_updated_ts, False
    )
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:03:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.last_reported.timestamp() == row.last_reported_ts
    assert lstate.last_changed_timestamp == row.last_changed_ts
    assert lstate.last_updated_timestamp == row.last_updated_ts
    assert lstate.last_reported_timestamp == row.last_reported_ts
