"""The tests for recorder platform migrating data from v30."""
# pylint: disable=invalid-name
from datetime import timedelta
import importlib
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import SQLITE_URL_PREFIX, core, statistics
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import EVENT_STATE_CHANGED, Event, EventOrigin, State
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from .common import wait_recording_done

from tests.common import get_test_home_assistant

ORIG_TZ = dt_util.DEFAULT_TIME_ZONE

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


def test_migrate_times(caplog: pytest.LogCaptureFixture, tmpdir) -> None:
    """Test we can migrate times."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]
    now = dt_util.utcnow()
    one_second_past = now - timedelta(seconds=1)
    now_timestamp = now.timestamp()
    one_second_past_timestamp = one_second_past.timestamp()

    mock_state = State(
        "sensor.test",
        "old",
        {"last_reset": now.isoformat()},
        last_changed=one_second_past,
        last_updated=now,
    )
    state_changed_event = Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.test",
            "old_state": None,
            "new_state": mock_state,
        },
        EventOrigin.local,
        time_fired=now,
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired=now,
    )

    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch.object(core, "EventData", old_db_schema.EventData), patch.object(
        core, "States", old_db_schema.States
    ), patch.object(
        core, "Events", old_db_schema.Events
    ), patch(
        CREATE_ENGINE_TARGET, new=_create_engine_test
    ):
        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(old_db_schema.Events.from_event(custom_event))
            session.add(old_db_schema.States.from_event(state_changed_event))

        hass.stop()

        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 23
    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)
    with session_scope(hass=hass) as session:
        result = list(
            session.query(recorder.db_schema.Events).where(
                recorder.db_schema.Events.event_type == "custom_event"
            )
        )
        assert len(result) == 1
        assert result[0].time_fired_ts == now_timestamp
        result = list(
            session.query(recorder.db_schema.States).where(
                recorder.db_schema.States.entity_id == "sensor.test"
            )
        )
        assert len(result) == 1
        assert result[0].last_changed_ts == one_second_past_timestamp
        assert result[0].last_updated_ts == now_timestamp

    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ
