"""Test data purging."""
from datetime import timedelta
import json

from homeassistant.components import recorder
from homeassistant.components.recorder.models import Events, RecorderRuns, States
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.util import session_scope
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done
from .conftest import SetupRecorderInstanceT


async def test_purge_old_states(
    hass: HomeAssistantType, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test deleting old states."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_states(hass, instance)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6
        assert states[0].old_state_id is None
        assert states[-1].old_state_id == states[-2].state_id

        events = session.query(Events).filter(Events.event_type == "state_changed")
        assert events.count() == 6

        # run purge_old_data()
        finished = purge_old_data(instance, 4, repack=False)
        assert not finished
        assert states.count() == 2

        states_after_purge = session.query(States)
        assert states_after_purge[1].old_state_id == states_after_purge[0].state_id
        assert states_after_purge[0].old_state_id is None

        finished = purge_old_data(instance, 4, repack=False)
        assert finished
        assert states.count() == 2


async def test_purge_old_events(
    hass: HomeAssistantType, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test deleting old events."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_events(hass, instance)

    with session_scope(hass=hass) as session:
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        # run purge_old_data()
        finished = purge_old_data(instance, 4, repack=False)
        assert not finished
        assert events.count() == 2

        # we should only have 2 events left
        finished = purge_old_data(instance, 4, repack=False)
        assert finished
        assert events.count() == 2


async def test_purge_old_recorder_runs(
    hass: HomeAssistantType, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test deleting old recorder runs keeps current run."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_recorder_runs(hass, instance)

    # make sure we start with 7 recorder runs
    with session_scope(hass=hass) as session:
        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7

        # run purge_old_data()
        finished = purge_old_data(instance, 0, repack=False)
        assert not finished

        finished = purge_old_data(instance, 0, repack=False)
        assert finished
        assert recorder_runs.count() == 1


async def test_purge_method(
    hass: HomeAssistantType,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog,
):
    """Test purge method."""
    instance = await async_setup_recorder_instance(hass)

    service_data = {"keep_days": 4}
    await _add_test_events(hass, instance)
    await _add_test_states(hass, instance)
    await _add_test_recorder_runs(hass, instance)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6

        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7

        await hass.async_block_till_done()
        await async_wait_recording_done(hass, instance)

        # run purge method - no service data, use defaults
        await hass.services.async_call("recorder", "purge")
        await hass.async_block_till_done()

        # Small wait for recorder thread
        await async_wait_recording_done(hass, instance)

        # only purged old events
        assert states.count() == 4
        assert events.count() == 4

        # run purge method - correct service data
        await hass.services.async_call("recorder", "purge", service_data=service_data)
        await hass.async_block_till_done()

        # Small wait for recorder thread
        await async_wait_recording_done(hass, instance)

        # we should only have 2 states left after purging
        assert states.count() == 2

        # now we should only have 2 events left
        assert events.count() == 2

        # now we should only have 3 recorder runs left
        assert recorder_runs.count() == 3

        assert not ("EVENT_TEST_PURGE" in (event.event_type for event in events.all()))

        # run purge method - correct service data, with repack
        service_data["repack"] = True
        await hass.services.async_call("recorder", "purge", service_data=service_data)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass, instance)
        assert "Vacuuming SQL DB to free space" in caplog.text


async def _add_test_states(hass: HomeAssistantType, instance: recorder.Recorder):
    """Add multiple states to the db for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    with recorder.session_scope(hass=hass) as session:
        old_state_id = None
        for event_id in range(6):
            if event_id < 2:
                timestamp = eleven_days_ago
                state = "autopurgeme"
            elif event_id < 4:
                timestamp = five_days_ago
                state = "purgeme"
            else:
                timestamp = utcnow
                state = "dontpurgeme"

            event = Events(
                event_type="state_changed",
                event_data="{}",
                origin="LOCAL",
                created=timestamp,
                time_fired=timestamp,
            )
            session.add(event)
            session.flush()
            state = States(
                entity_id="test.recorder2",
                domain="sensor",
                state=state,
                attributes=json.dumps(attributes),
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                event_id=event.event_id,
                old_state_id=old_state_id,
            )
            session.add(state)
            session.flush()
            old_state_id = state.state_id


async def _add_test_events(hass: HomeAssistantType, instance: recorder.Recorder):
    """Add a few events for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    with recorder.session_scope(hass=hass) as session:
        for event_id in range(6):
            if event_id < 2:
                timestamp = eleven_days_ago
                event_type = "EVENT_TEST_AUTOPURGE"
            elif event_id < 4:
                timestamp = five_days_ago
                event_type = "EVENT_TEST_PURGE"
            else:
                timestamp = utcnow
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


async def _add_test_recorder_runs(hass: HomeAssistantType, instance: recorder.Recorder):
    """Add a few recorder_runs for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    with recorder.session_scope(hass=hass) as session:
        for rec_id in range(6):
            if rec_id < 2:
                timestamp = eleven_days_ago
            elif rec_id < 4:
                timestamp = five_days_ago
            else:
                timestamp = utcnow

            session.add(
                RecorderRuns(
                    start=timestamp,
                    created=dt_util.utcnow(),
                    end=timestamp + timedelta(days=1),
                )
            )
