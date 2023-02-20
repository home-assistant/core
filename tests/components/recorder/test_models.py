"""The tests for the Recorder component."""
from datetime import datetime, timedelta
from unittest.mock import PropertyMock

from freezegun import freeze_time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from homeassistant.components.recorder.const import SupportedDialect
from homeassistant.components.recorder.db_schema import (
    Base,
    EventData,
    Events,
    RecorderRuns,
    StateAttributes,
    States,
)
from homeassistant.components.recorder.models import (
    LazyState,
    process_datetime_to_timestamp,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
)
from homeassistant.const import EVENT_STATE_CHANGED
import homeassistant.core as ha
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import InvalidEntityFormatError
from homeassistant.util import dt, dt as dt_util


def test_from_event_to_db_event() -> None:
    """Test converting event to db event."""
    event = ha.Event("test_event", {"some_data": 15})
    db_event = Events.from_event(event)
    dialect = SupportedDialect.MYSQL
    db_event.event_data = EventData.shared_data_bytes_from_event(event, dialect)
    assert event.as_dict() == db_event.to_native().as_dict()


def test_from_event_to_db_state() -> None:
    """Test converting event to db state."""
    state = ha.State("sensor.temperature", "18")
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
        event, {}, {}, dialect
    )
    assert db_attrs.to_native() == attrs


def test_repr() -> None:
    """Test converting event to db state repr."""
    attrs = {"this_attr": True}
    fixed_time = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC, microsecond=432432)
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
        time_fired=fixed_time,
    )
    assert "2016-07-09 11:00:00+00:00" in repr(States.from_event(event))
    assert "2016-07-09 11:00:00+00:00" in repr(Events.from_event(event))


def test_states_repr_without_timestamp() -> None:
    """Test repr for a state without last_updated_ts."""
    fixed_time = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC, microsecond=432432)
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
    fixed_time = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC, microsecond=432432)
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
    assert db_state.last_updated_ts == event.time_fired.timestamp()


def test_entity_ids(recorder_db_url: str) -> None:
    """Test if entity ids helper method works."""
    if recorder_db_url.startswith("mysql://"):
        # Dropping the database after this test will fail on MySQL
        # because it will create an InnoDB deadlock.
        return
    engine = create_engine(recorder_db_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    session = scoped_session(session_factory)
    session.query(Events).delete()
    session.query(States).delete()
    session.query(RecorderRuns).delete()

    run = RecorderRuns(
        start=datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC),
        end=datetime(2016, 7, 9, 23, 0, 0, tzinfo=dt.UTC),
        closed_incorrect=False,
        created=datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC),
    )

    session.add(run)
    session.commit()

    before_run = datetime(2016, 7, 9, 8, 0, 0, tzinfo=dt.UTC)
    in_run = datetime(2016, 7, 9, 13, 0, 0, tzinfo=dt.UTC)
    in_run2 = datetime(2016, 7, 9, 15, 0, 0, tzinfo=dt.UTC)
    in_run3 = datetime(2016, 7, 9, 18, 0, 0, tzinfo=dt.UTC)
    after_run = datetime(2016, 7, 9, 23, 30, 0, tzinfo=dt.UTC)

    assert run.to_native() == run
    assert run.entity_ids() == []

    session.add(
        States(
            entity_id="sensor.temperature",
            state="20",
            last_changed=before_run,
            last_updated=before_run,
        )
    )
    session.add(
        States(
            entity_id="sensor.sound",
            state="10",
            last_changed=after_run,
            last_updated=after_run,
        )
    )

    session.add(
        States(
            entity_id="sensor.humidity",
            state="76",
            last_changed=in_run,
            last_updated=in_run,
        )
    )
    session.add(
        States(
            entity_id="sensor.lux",
            state="5",
            last_changed=in_run3,
            last_updated=in_run3,
        )
    )

    assert sorted(run.entity_ids()) == ["sensor.humidity", "sensor.lux"]
    assert run.entity_ids(in_run2) == ["sensor.humidity"]


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
    datetime_with_tzinfo = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC)
    datetime_without_tzinfo = datetime(2016, 7, 9, 11, 0, 0)
    est = dt_util.get_time_zone("US/Eastern")
    datetime_est_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=est)
    nst = dt_util.get_time_zone("Canada/Newfoundland")
    datetime_nst_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=nst)
    hst = dt_util.get_time_zone("US/Hawaii")
    datetime_hst_timezone = datetime(2016, 7, 9, 11, 0, 0, tzinfo=hst)

    assert process_timestamp(datetime_with_tzinfo) == datetime(
        2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC
    )
    assert process_timestamp(datetime_without_tzinfo) == datetime(
        2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC
    )
    assert process_timestamp(datetime_est_timezone) == datetime(
        2016, 7, 9, 15, 0, tzinfo=dt.UTC
    )
    assert process_timestamp(datetime_nst_timezone) == datetime(
        2016, 7, 9, 13, 30, tzinfo=dt.UTC
    )
    assert process_timestamp(datetime_hst_timezone) == datetime(
        2016, 7, 9, 21, 0, tzinfo=dt.UTC
    )
    assert process_timestamp(None) is None


async def test_process_timestamp_to_utc_isoformat() -> None:
    """Test processing time stamp to UTC isoformat."""
    datetime_with_tzinfo = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC)
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
        "state_changed", {"some": "attr"}, ha.EventOrigin.local, dt_util.utcnow()
    )
    db_event = Events.from_event(event)
    dialect = SupportedDialect.MYSQL
    db_event.event_data = EventData.shared_data_bytes_from_event(event, dialect)
    native = db_event.to_native()
    assert native.as_dict() == event.as_dict()

    native = Events.from_event(event).to_native()
    event.data = {}
    assert native.as_dict() == event.as_dict()


async def test_lazy_state_handles_include_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState class handles invalid json."""
    row = PropertyMock(
        entity_id="sensor.invalid",
        shared_attrs="{INVALID_JSON}",
    )
    assert LazyState(row, {}, None).attributes == {}
    assert "Error converting row to state attributes" in caplog.text


async def test_lazy_state_prefers_shared_attrs_over_attrs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState prefers shared_attrs over attributes."""
    row = PropertyMock(
        entity_id="sensor.invalid",
        shared_attrs='{"shared":true}',
        attributes='{"shared":false}',
    )
    assert LazyState(row, {}, None).attributes == {"shared": True}


async def test_lazy_state_handles_different_last_updated_and_last_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles different last_updated and last_changed."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        shared_attrs='{"shared":true}',
        last_updated_ts=now.timestamp(),
        last_changed_ts=(now - timedelta(seconds=60)).timestamp(),
    )
    lstate = LazyState(row, {}, None)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:03:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }


async def test_lazy_state_handles_same_last_updated_and_last_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the LazyState handles same last_updated and last_changed."""
    now = datetime(2021, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    row = PropertyMock(
        entity_id="sensor.valid",
        state="off",
        shared_attrs='{"shared":true}',
        last_updated_ts=now.timestamp(),
        last_changed_ts=now.timestamp(),
    )
    lstate = LazyState(row, {}, None)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    assert lstate.last_updated.timestamp() == row.last_updated_ts
    assert lstate.last_changed.timestamp() == row.last_changed_ts
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2021-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    lstate.last_updated = datetime(2020, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2021-06-12T03:04:01.000323+00:00",
        "last_updated": "2020-06-12T03:04:01.000323+00:00",
        "state": "off",
    }
    lstate.last_changed = datetime(2020, 6, 12, 3, 4, 1, 323, tzinfo=dt_util.UTC)
    assert lstate.as_dict() == {
        "attributes": {"shared": True},
        "entity_id": "sensor.valid",
        "last_changed": "2020-06-12T03:04:01.000323+00:00",
        "last_updated": "2020-06-12T03:04:01.000323+00:00",
        "state": "off",
    }


@pytest.mark.parametrize(
    "time_zone", ["Europe/Berlin", "America/Chicago", "US/Hawaii", "UTC"]
)
def test_process_datetime_to_timestamp(time_zone, hass: HomeAssistant) -> None:
    """Test we can handle processing database datatimes to timestamps."""
    hass.config.set_time_zone(time_zone)
    utc_now = dt_util.utcnow()
    assert process_datetime_to_timestamp(utc_now) == utc_now.timestamp()
    now = dt_util.now()
    assert process_datetime_to_timestamp(now) == now.timestamp()


@pytest.mark.parametrize(
    "time_zone", ["Europe/Berlin", "America/Chicago", "US/Hawaii", "UTC"]
)
def test_process_datetime_to_timestamp_freeze_time(
    time_zone, hass: HomeAssistant
) -> None:
    """Test we can handle processing database datatimes to timestamps.

    This test freezes time to make sure everything matches.
    """
    hass.config.set_time_zone(time_zone)
    utc_now = dt_util.utcnow()
    with freeze_time(utc_now):
        epoch = utc_now.timestamp()
        assert process_datetime_to_timestamp(dt_util.utcnow()) == epoch
        now = dt_util.now()
        assert process_datetime_to_timestamp(now) == epoch


@pytest.mark.parametrize(
    "time_zone", ["Europe/Berlin", "America/Chicago", "US/Hawaii", "UTC"]
)
async def test_process_datetime_to_timestamp_mirrors_utc_isoformat_behavior(
    time_zone, hass: HomeAssistant
) -> None:
    """Test process_datetime_to_timestamp mirrors process_timestamp_to_utc_isoformat."""
    hass.config.set_time_zone(time_zone)
    datetime_with_tzinfo = datetime(2016, 7, 9, 11, 0, 0, tzinfo=dt.UTC)
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
        process_datetime_to_timestamp(datetime_with_tzinfo)
        == dt_util.parse_datetime("2016-07-09T11:00:00+00:00").timestamp()
    )
    assert (
        process_datetime_to_timestamp(datetime_without_tzinfo)
        == dt_util.parse_datetime("2016-07-09T11:00:00+00:00").timestamp()
    )
    assert (
        process_datetime_to_timestamp(datetime_est_timezone)
        == dt_util.parse_datetime("2016-07-09T15:00:00+00:00").timestamp()
    )
    assert (
        process_datetime_to_timestamp(datetime_nst_timezone)
        == dt_util.parse_datetime("2016-07-09T13:30:00+00:00").timestamp()
    )
    assert (
        process_datetime_to_timestamp(datetime_hst_timezone)
        == dt_util.parse_datetime("2016-07-09T21:00:00+00:00").timestamp()
    )
