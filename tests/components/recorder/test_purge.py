"""Test data purging."""
from datetime import datetime, timedelta
import json
from unittest.mock import patch

from homeassistant.components import recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import Events, RecorderRuns, States
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.util import session_scope
from homeassistant.util import dt as dt_util

from .common import wait_recording_done


def test_purge_old_states(hass, hass_recorder):
    """Test deleting old states."""
    hass = hass_recorder()
    _add_test_states(hass)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6

        # run purge_old_data()
        finished = purge_old_data(hass.data[DATA_INSTANCE], 4, repack=False)
        assert not finished
        assert states.count() == 4

        finished = purge_old_data(hass.data[DATA_INSTANCE], 4, repack=False)
        assert not finished
        assert states.count() == 2

        finished = purge_old_data(hass.data[DATA_INSTANCE], 4, repack=False)
        assert finished
        assert states.count() == 2


def test_purge_old_events(hass, hass_recorder):
    """Test deleting old events."""
    hass = hass_recorder()
    _add_test_events(hass)

    with session_scope(hass=hass) as session:
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        # run purge_old_data()
        finished = purge_old_data(hass.data[DATA_INSTANCE], 4, repack=False)
        assert not finished
        assert events.count() == 4

        finished = purge_old_data(hass.data[DATA_INSTANCE], 4, repack=False)
        assert not finished
        assert events.count() == 2

        # we should only have 2 events left
        finished = purge_old_data(hass.data[DATA_INSTANCE], 4, repack=False)
        assert finished
        assert events.count() == 2


def test_purge_old_recorder_runs(hass, hass_recorder):
    """Test deleting old recorder runs keeps current run."""
    hass = hass_recorder()
    _add_test_recorder_runs(hass)

    # make sure we start with 7 recorder runs
    with session_scope(hass=hass) as session:
        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7

        # run purge_old_data()
        finished = purge_old_data(hass.data[DATA_INSTANCE], 0, repack=False)
        assert finished
        assert recorder_runs.count() == 1


def test_purge_method(hass, hass_recorder):
    """Test purge method."""
    hass = hass_recorder()
    service_data = {"keep_days": 4}
    _add_test_events(hass)
    _add_test_states(hass)
    _add_test_recorder_runs(hass)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6

        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7

        hass.data[DATA_INSTANCE].block_till_done()
        wait_recording_done(hass)

        # run purge method - no service data, use defaults
        hass.services.call("recorder", "purge")
        hass.block_till_done()

        # Small wait for recorder thread
        hass.data[DATA_INSTANCE].block_till_done()
        wait_recording_done(hass)

        # only purged old events
        assert states.count() == 4
        assert events.count() == 4

        # run purge method - correct service data
        hass.services.call("recorder", "purge", service_data=service_data)
        hass.block_till_done()

        # Small wait for recorder thread
        hass.data[DATA_INSTANCE].block_till_done()
        wait_recording_done(hass)

        # we should only have 2 states left after purging
        assert states.count() == 2

        # now we should only have 2 events left
        assert events.count() == 2

        # now we should only have 3 recorder runs left
        assert recorder_runs.count() == 3

        assert not ("EVENT_TEST_PURGE" in (event.event_type for event in events.all()))

        # run purge method - correct service data, with repack
        with patch("homeassistant.components.recorder.purge._LOGGER") as mock_logger:
            service_data["repack"] = True
            hass.services.call("recorder", "purge", service_data=service_data)
            hass.block_till_done()
            hass.data[DATA_INSTANCE].block_till_done()
            wait_recording_done(hass)
            assert (
                mock_logger.debug.mock_calls[5][1][0]
                == "Vacuuming SQL DB to free space"
            )


def _add_test_states(hass):
    """Add multiple states to the db for testing."""
    now = datetime.now()
    five_days_ago = now - timedelta(days=5)
    eleven_days_ago = now - timedelta(days=11)
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.block_till_done()
    hass.data[DATA_INSTANCE].block_till_done()
    wait_recording_done(hass)

    with recorder.session_scope(hass=hass) as session:
        for event_id in range(6):
            if event_id < 2:
                timestamp = eleven_days_ago
                state = "autopurgeme"
            elif event_id < 4:
                timestamp = five_days_ago
                state = "purgeme"
            else:
                timestamp = now
                state = "dontpurgeme"

            session.add(
                States(
                    entity_id="test.recorder2",
                    domain="sensor",
                    state=state,
                    attributes=json.dumps(attributes),
                    last_changed=timestamp,
                    last_updated=timestamp,
                    created=timestamp,
                    event_id=event_id + 1000,
                )
            )


def _add_test_events(hass):
    """Add a few events for testing."""
    now = datetime.now()
    five_days_ago = now - timedelta(days=5)
    eleven_days_ago = now - timedelta(days=11)
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    hass.block_till_done()
    hass.data[DATA_INSTANCE].block_till_done()
    wait_recording_done(hass)

    with recorder.session_scope(hass=hass) as session:
        for event_id in range(6):
            if event_id < 2:
                timestamp = eleven_days_ago
                event_type = "EVENT_TEST_AUTOPURGE"
            elif event_id < 4:
                timestamp = five_days_ago
                event_type = "EVENT_TEST_PURGE"
            else:
                timestamp = now
                event_type = "EVENT_TEST"

            session.add(
                Events(
                    event_type=event_type,
                    event_data=json.dumps(event_data),
                    origin="LOCAL",
                    created=timestamp,
                    time_fired=timestamp,
                )
            )


def _add_test_recorder_runs(hass):
    """Add a few recorder_runs for testing."""
    now = datetime.now()
    five_days_ago = now - timedelta(days=5)
    eleven_days_ago = now - timedelta(days=11)

    hass.block_till_done()
    hass.data[DATA_INSTANCE].block_till_done()
    wait_recording_done(hass)

    with recorder.session_scope(hass=hass) as session:
        for rec_id in range(6):
            if rec_id < 2:
                timestamp = eleven_days_ago
            elif rec_id < 4:
                timestamp = five_days_ago
            else:
                timestamp = now

            session.add(
                RecorderRuns(
                    start=timestamp,
                    created=dt_util.utcnow(),
                    end=timestamp + timedelta(days=1),
                )
            )
