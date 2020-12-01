"""Test to verify that Home Assistant core works."""
# pylint: disable=protected-access
import asyncio
from datetime import datetime, timedelta
import functools
import logging
import os
from tempfile import TemporaryDirectory

import pytest
import pytz
import voluptuous as vol

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_NOW,
    ATTR_SECONDS,
    CONF_UNIT_SYSTEM,
    EVENT_CALL_SERVICE,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED,
    EVENT_TIMER_OUT_OF_SYNC,
    MATCH_ALL,
    __version__,
)
import homeassistant.core as ha
from homeassistant.exceptions import (
    InvalidEntityFormatError,
    InvalidStateError,
    ServiceNotFound,
)
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from tests.async_mock import MagicMock, Mock, PropertyMock, patch
from tests.common import async_capture_events, async_mock_service

PST = pytz.timezone("America/Los_Angeles")


def test_split_entity_id():
    """Test split_entity_id."""
    assert ha.split_entity_id("domain.object_id") == ["domain", "object_id"]


def test_async_add_hass_job_schedule_callback():
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_hass_job_schedule_partial_callback():
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock()
    job = MagicMock()
    partial = functools.partial(ha.callback(job))

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(partial))
    assert len(hass.loop.call_soon.mock_calls) == 1
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_hass_job_schedule_coroutinefunction(loop):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=loop))

    async def job():
        pass

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(job))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_hass_job_schedule_partial_coroutinefunction(loop):
    """Test that we schedule partial coros and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=loop))

    async def job():
        pass

    partial = functools.partial(job)

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(partial))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_add_job_add_hass_threaded_job_to_pool():
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock()

    def job():
        pass

    ha.HomeAssistant.async_add_hass_job(hass, ha.HassJob(job))
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 0
    assert len(hass.loop.run_in_executor.mock_calls) == 1


def test_async_create_task_schedule_coroutine(loop):
    """Test that we schedule coroutines and add jobs to the job pool."""
    hass = MagicMock(loop=MagicMock(wraps=loop))

    async def job():
        pass

    ha.HomeAssistant.async_create_task(hass, job())
    assert len(hass.loop.call_soon.mock_calls) == 0
    assert len(hass.loop.create_task.mock_calls) == 1
    assert len(hass.add_job.mock_calls) == 0


def test_async_run_hass_job_calls_callback():
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(ha.callback(job)))
    assert len(calls) == 1
    assert len(hass.async_add_job.mock_calls) == 0


def test_async_run_hass_job_delegates_non_async():
    """Test that the callback annotation is respected."""
    hass = MagicMock()
    calls = []

    def job():
        calls.append(1)

    ha.HomeAssistant.async_run_hass_job(hass, ha.HassJob(job))
    assert len(calls) == 0
    assert len(hass.async_add_hass_job.mock_calls) == 1


async def test_stage_shutdown(hass):
    """Simulate a shutdown, test calling stuff."""
    test_stop = async_capture_events(hass, EVENT_HOMEASSISTANT_STOP)
    test_final_write = async_capture_events(hass, EVENT_HOMEASSISTANT_FINAL_WRITE)
    test_close = async_capture_events(hass, EVENT_HOMEASSISTANT_CLOSE)
    test_all = async_capture_events(hass, MATCH_ALL)

    await hass.async_stop()

    assert len(test_stop) == 1
    assert len(test_close) == 1
    assert len(test_final_write) == 1
    assert len(test_all) == 2


async def test_pending_sheduler(hass):
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(3):
        hass.async_add_job(test_coro())

    await asyncio.wait(hass._pending_tasks)

    assert len(hass._pending_tasks) == 3
    assert len(call_count) == 3


async def test_async_add_job_pending_tasks_coro(hass):
    """Add a coro to pending tasks."""
    call_count = []

    async def test_coro():
        """Test Coro."""
        call_count.append("call")

    for _ in range(2):
        hass.add_job(test_coro())

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    await wait_finish_callback()

    assert len(hass._pending_tasks) == 2
    await hass.async_block_till_done()
    assert len(call_count) == 2


async def test_async_add_job_pending_tasks_executor(hass):
    """Run an executor in pending tasks."""
    call_count = []

    def test_executor():
        """Test executor."""
        call_count.append("call")

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    for _ in range(2):
        hass.async_add_job(test_executor)

    await wait_finish_callback()

    assert len(hass._pending_tasks) == 2
    await hass.async_block_till_done()
    assert len(call_count) == 2


async def test_async_add_job_pending_tasks_callback(hass):
    """Run a callback in pending tasks."""
    call_count = []

    @ha.callback
    def test_callback():
        """Test callback."""
        call_count.append("call")

    async def wait_finish_callback():
        """Wait until all stuff is scheduled."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    for _ in range(2):
        hass.async_add_job(test_callback)

    await wait_finish_callback()

    await hass.async_block_till_done()

    assert len(hass._pending_tasks) == 0
    assert len(call_count) == 2


async def test_add_job_with_none(hass):
    """Try to add a job with None as function."""
    with pytest.raises(ValueError):
        hass.async_add_job(None, "test_arg")


def test_event_eq():
    """Test events."""
    now = dt_util.utcnow()
    data = {"some": "attr"}
    context = ha.Context()
    event1, event2 = [
        ha.Event("some_type", data, time_fired=now, context=context) for _ in range(2)
    ]

    assert event1 == event2


def test_event_repr():
    """Test that Event repr method works."""
    assert str(ha.Event("TestEvent")) == "<Event TestEvent[L]>"

    assert (
        str(ha.Event("TestEvent", {"beer": "nice"}, ha.EventOrigin.remote))
        == "<Event TestEvent[R]: beer=nice>"
    )


def test_event_as_dict():
    """Test an Event as dictionary."""
    event_type = "some_type"
    now = dt_util.utcnow()
    data = {"some": "attr"}

    event = ha.Event(event_type, data, ha.EventOrigin.local, now)
    expected = {
        "event_type": event_type,
        "data": data,
        "origin": "LOCAL",
        "time_fired": now.isoformat(),
        "context": {
            "id": event.context.id,
            "parent_id": None,
            "user_id": event.context.user_id,
        },
    }
    assert event.as_dict() == expected
    # 2nd time to verify cache
    assert event.as_dict() == expected


def test_state_as_dict():
    """Test a State as dictionary."""
    last_time = datetime(1984, 12, 8, 12, 0, 0)
    state = ha.State(
        "happy.happy",
        "on",
        {"pig": "dog"},
        last_updated=last_time,
        last_changed=last_time,
    )
    expected = {
        "context": {
            "id": state.context.id,
            "parent_id": None,
            "user_id": state.context.user_id,
        },
        "entity_id": "happy.happy",
        "attributes": {"pig": "dog"},
        "last_changed": last_time.isoformat(),
        "last_updated": last_time.isoformat(),
        "state": "on",
    }
    assert state.as_dict() == expected
    # 2nd time to verify cache
    assert state.as_dict() == expected
    assert state.as_dict() is state.as_dict()


async def test_eventbus_add_remove_listener(hass):
    """Test remove_listener method."""
    old_count = len(hass.bus.async_listeners())

    def listener(_):
        pass

    unsub = hass.bus.async_listen("test", listener)

    assert old_count + 1 == len(hass.bus.async_listeners())

    # Remove listener
    unsub()
    assert old_count == len(hass.bus.async_listeners())

    # Should do nothing now
    unsub()


async def test_eventbus_unsubscribe_listener(hass):
    """Test unsubscribe listener from returned function."""
    calls = []

    @ha.callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    unsub = hass.bus.async_listen("test", listener)

    hass.bus.async_fire("test")
    await hass.async_block_till_done()

    assert len(calls) == 1

    unsub()

    hass.bus.async_fire("event")
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_eventbus_listen_once_event_with_callback(hass):
    """Test listen_once_event method."""
    runs = []

    @ha.callback
    def event_handler(event):
        runs.append(event)

    hass.bus.async_listen_once("test_event", event_handler)

    hass.bus.async_fire("test_event")
    # Second time it should not increase runs
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()
    assert len(runs) == 1


async def test_eventbus_listen_once_event_with_coroutine(hass):
    """Test listen_once_event method."""
    runs = []

    async def event_handler(event):
        runs.append(event)

    hass.bus.async_listen_once("test_event", event_handler)

    hass.bus.async_fire("test_event")
    # Second time it should not increase runs
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()
    assert len(runs) == 1


async def test_eventbus_listen_once_event_with_thread(hass):
    """Test listen_once_event method."""
    runs = []

    def event_handler(event):
        runs.append(event)

    hass.bus.async_listen_once("test_event", event_handler)

    hass.bus.async_fire("test_event")
    # Second time it should not increase runs
    hass.bus.async_fire("test_event")

    await hass.async_block_till_done()
    assert len(runs) == 1


async def test_eventbus_thread_event_listener(hass):
    """Test thread event listener."""
    thread_calls = []

    def thread_listener(event):
        thread_calls.append(event)

    hass.bus.async_listen("test_thread", thread_listener)
    hass.bus.async_fire("test_thread")
    await hass.async_block_till_done()
    assert len(thread_calls) == 1


async def test_eventbus_callback_event_listener(hass):
    """Test callback event listener."""
    callback_calls = []

    @ha.callback
    def callback_listener(event):
        callback_calls.append(event)

    hass.bus.async_listen("test_callback", callback_listener)
    hass.bus.async_fire("test_callback")
    await hass.async_block_till_done()
    assert len(callback_calls) == 1


async def test_eventbus_coroutine_event_listener(hass):
    """Test coroutine event listener."""
    coroutine_calls = []

    async def coroutine_listener(event):
        coroutine_calls.append(event)

    hass.bus.async_listen("test_coroutine", coroutine_listener)
    hass.bus.async_fire("test_coroutine")
    await hass.async_block_till_done()
    assert len(coroutine_calls) == 1


def test_state_init():
    """Test state.init."""
    with pytest.raises(InvalidEntityFormatError):
        ha.State("invalid_entity_format", "test_state")

    with pytest.raises(InvalidStateError):
        ha.State("domain.long_state", "t" * 256)


def test_state_domain():
    """Test domain."""
    state = ha.State("some_domain.hello", "world")
    assert state.domain == "some_domain"


def test_state_object_id():
    """Test object ID."""
    state = ha.State("domain.hello", "world")
    assert state.object_id == "hello"


def test_state_name_if_no_friendly_name_attr():
    """Test if there is no friendly name."""
    state = ha.State("domain.hello_world", "world")
    assert state.name == "hello world"


def test_state_name_if_friendly_name_attr():
    """Test if there is a friendly name."""
    name = "Some Unique Name"
    state = ha.State("domain.hello_world", "world", {ATTR_FRIENDLY_NAME: name})
    assert state.name == name


def test_state_dict_conversion():
    """Test conversion of dict."""
    state = ha.State("domain.hello", "world", {"some": "attr"})
    assert state == ha.State.from_dict(state.as_dict())


def test_state_dict_conversion_with_wrong_data():
    """Test conversion with wrong data."""
    assert ha.State.from_dict(None) is None
    assert ha.State.from_dict({"state": "yes"}) is None
    assert ha.State.from_dict({"entity_id": "yes"}) is None
    # Make sure invalid context data doesn't crash
    wrong_context = ha.State.from_dict(
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "context": {"id": "123", "non-existing": "crash"},
        }
    )
    assert wrong_context is not None
    assert wrong_context.context.id == "123"


def test_state_repr():
    """Test state.repr."""
    assert (
        str(ha.State("happy.happy", "on", last_changed=datetime(1984, 12, 8, 12, 0, 0)))
        == "<state happy.happy=on @ 1984-12-08T12:00:00+00:00>"
    )

    assert (
        str(
            ha.State(
                "happy.happy",
                "on",
                {"brightness": 144},
                datetime(1984, 12, 8, 12, 0, 0),
            )
        )
        == "<state happy.happy=on; brightness=144 @ "
        "1984-12-08T12:00:00+00:00>"
    )


async def test_statemachine_is_state(hass):
    """Test is_state method."""
    hass.states.async_set("light.bowl", "on", {})
    assert hass.states.is_state("light.Bowl", "on")
    assert not hass.states.is_state("light.Bowl", "off")
    assert not hass.states.is_state("light.Non_existing", "on")


async def test_statemachine_entity_ids(hass):
    """Test get_entity_ids method."""
    hass.states.async_set("light.bowl", "on", {})
    hass.states.async_set("SWITCH.AC", "off", {})
    ent_ids = hass.states.async_entity_ids()
    assert len(ent_ids) == 2
    assert "light.bowl" in ent_ids
    assert "switch.ac" in ent_ids

    ent_ids = hass.states.async_entity_ids("light")
    assert len(ent_ids) == 1
    assert "light.bowl" in ent_ids

    states = sorted(state.entity_id for state in hass.states.async_all())
    assert states == ["light.bowl", "switch.ac"]


async def test_statemachine_remove(hass):
    """Test remove method."""
    hass.states.async_set("light.bowl", "on", {})
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    assert "light.bowl" in hass.states.async_entity_ids()
    assert hass.states.async_remove("light.bowl")
    await hass.async_block_till_done()

    assert "light.bowl" not in hass.states.async_entity_ids()
    assert len(events) == 1
    assert events[0].data.get("entity_id") == "light.bowl"
    assert events[0].data.get("old_state") is not None
    assert events[0].data["old_state"].entity_id == "light.bowl"
    assert events[0].data.get("new_state") is None

    # If it does not exist, we should get False
    assert not hass.states.async_remove("light.Bowl")
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_statemachine_case_insensitivty(hass):
    """Test insensitivty."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    hass.states.async_set("light.BOWL", "off")
    await hass.async_block_till_done()

    assert hass.states.is_state("light.bowl", "off")
    assert len(events) == 1


async def test_statemachine_last_changed_not_updated_on_same_state(hass):
    """Test to not update the existing, same state."""
    hass.states.async_set("light.bowl", "on", {})
    state = hass.states.get("light.Bowl")

    future = dt_util.utcnow() + timedelta(hours=10)

    with patch("homeassistant.util.dt.utcnow", return_value=future):
        hass.states.async_set("light.Bowl", "on", {"attr": "triggers_change"})
        await hass.async_block_till_done()

    state2 = hass.states.get("light.Bowl")
    assert state2 is not None
    assert state.last_changed == state2.last_changed


async def test_statemachine_force_update(hass):
    """Test force update option."""
    hass.states.async_set("light.bowl", "on", {})
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    hass.states.async_set("light.bowl", "on")
    await hass.async_block_till_done()
    assert len(events) == 0

    hass.states.async_set("light.bowl", "on", None, True)
    await hass.async_block_till_done()
    assert len(events) == 1


def test_service_call_repr():
    """Test ServiceCall repr."""
    call = ha.ServiceCall("homeassistant", "start")
    assert str(call) == f"<ServiceCall homeassistant.start (c:{call.context.id})>"

    call2 = ha.ServiceCall("homeassistant", "start", {"fast": "yes"})
    assert (
        str(call2)
        == f"<ServiceCall homeassistant.start (c:{call2.context.id}): fast=yes>"
    )


async def test_serviceregistry_has_service(hass):
    """Test has_service method."""
    hass.services.async_register("test_domain", "test_service", lambda call: None)
    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service("tesT_domaiN", "tesT_servicE")
    assert not hass.services.has_service("test_domain", "non_existing")
    assert not hass.services.has_service("non_existing", "test_service")


async def test_serviceregistry_call_with_blocking_done_in_time(hass):
    """Test call with blocking."""
    registered_events = async_capture_events(hass, EVENT_SERVICE_REGISTERED)
    calls = async_mock_service(hass, "test_domain", "register_calls")
    await hass.async_block_till_done()

    assert len(registered_events) == 1
    assert registered_events[0].data["domain"] == "test_domain"
    assert registered_events[0].data["service"] == "register_calls"

    assert await hass.services.async_call(
        "test_domain", "REGISTER_CALLS", blocking=True
    )
    assert len(calls) == 1


async def test_serviceregistry_call_non_existing_with_blocking(hass):
    """Test non-existing with blocking."""
    with pytest.raises(ha.ServiceNotFound):
        await hass.services.async_call("test_domain", "i_do_not_exist", blocking=True)


async def test_serviceregistry_async_service(hass):
    """Test registering and calling an async service."""
    calls = []

    async def service_handler(call):
        """Service handler coroutine."""
        calls.append(call)

    hass.services.async_register("test_domain", "register_calls", service_handler)

    assert await hass.services.async_call(
        "test_domain", "REGISTER_CALLS", blocking=True
    )
    assert len(calls) == 1


async def test_serviceregistry_async_service_partial(hass):
    """Test registering and calling an wrapped async service."""
    calls = []

    async def service_handler(call):
        """Service handler coroutine."""
        calls.append(call)

    hass.services.async_register(
        "test_domain", "register_calls", functools.partial(service_handler)
    )
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        "test_domain", "REGISTER_CALLS", blocking=True
    )
    assert len(calls) == 1


async def test_serviceregistry_callback_service(hass):
    """Test registering and calling an async service."""
    calls = []

    @ha.callback
    def service_handler(call):
        """Service handler coroutine."""
        calls.append(call)

    hass.services.async_register("test_domain", "register_calls", service_handler)

    assert await hass.services.async_call(
        "test_domain", "REGISTER_CALLS", blocking=True
    )
    assert len(calls) == 1


async def test_serviceregistry_remove_service(hass):
    """Test remove service."""
    calls_remove = async_capture_events(hass, EVENT_SERVICE_REMOVED)

    hass.services.async_register("test_domain", "test_service", lambda call: None)
    assert hass.services.has_service("test_Domain", "test_Service")

    hass.services.async_remove("test_Domain", "test_Service")
    await hass.async_block_till_done()

    assert not hass.services.has_service("test_Domain", "test_Service")
    assert len(calls_remove) == 1
    assert calls_remove[-1].data["domain"] == "test_domain"
    assert calls_remove[-1].data["service"] == "test_service"


async def test_serviceregistry_service_that_not_exists(hass):
    """Test remove service that not exists."""
    calls_remove = async_capture_events(hass, EVENT_SERVICE_REMOVED)
    assert not hass.services.has_service("test_xxx", "test_yyy")
    hass.services.async_remove("test_xxx", "test_yyy")
    await hass.async_block_till_done()
    assert len(calls_remove) == 0

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call("test_do_not", "exist", {})


async def test_serviceregistry_async_service_raise_exception(hass):
    """Test registering and calling an async service raise exception."""

    async def service_handler(_):
        """Service handler coroutine."""
        raise ValueError

    hass.services.async_register("test_domain", "register_calls", service_handler)

    with pytest.raises(ValueError):
        assert await hass.services.async_call(
            "test_domain", "REGISTER_CALLS", blocking=True
        )

    # Non-blocking service call never throw exception
    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=False)
    await hass.async_block_till_done()


async def test_serviceregistry_callback_service_raise_exception(hass):
    """Test registering and calling an callback service raise exception."""

    @ha.callback
    def service_handler(_):
        """Service handler coroutine."""
        raise ValueError

    hass.services.async_register("test_domain", "register_calls", service_handler)

    with pytest.raises(ValueError):
        assert await hass.services.async_call(
            "test_domain", "REGISTER_CALLS", blocking=True
        )

    # Non-blocking service call never throw exception
    await hass.services.async_call("test_domain", "REGISTER_CALLS", blocking=False)
    await hass.async_block_till_done()


def test_config_defaults():
    """Test config defaults."""
    hass = Mock()
    config = ha.Config(hass)
    assert config.hass is hass
    assert config.latitude == 0
    assert config.longitude == 0
    assert config.elevation == 0
    assert config.location_name == "Home"
    assert config.time_zone == dt_util.UTC
    assert config.internal_url is None
    assert config.external_url is None
    assert config.config_source == "default"
    assert config.skip_pip is False
    assert config.components == set()
    assert config.api is None
    assert config.config_dir is None
    assert config.allowlist_external_dirs == set()
    assert config.allowlist_external_urls == set()
    assert config.media_dirs == {}
    assert config.safe_mode is False
    assert config.legacy_templates is False


def test_config_path_with_file():
    """Test get_config_path method."""
    config = ha.Config(None)
    config.config_dir = "/test/ha-config"
    assert config.path("test.conf") == "/test/ha-config/test.conf"


def test_config_path_with_dir_and_file():
    """Test get_config_path method."""
    config = ha.Config(None)
    config.config_dir = "/test/ha-config"
    assert config.path("dir", "test.conf") == "/test/ha-config/dir/test.conf"


def test_config_as_dict():
    """Test as dict."""
    config = ha.Config(None)
    config.config_dir = "/test/ha-config"
    config.hass = MagicMock()
    type(config.hass.state).value = PropertyMock(return_value="RUNNING")
    expected = {
        "latitude": 0,
        "longitude": 0,
        "elevation": 0,
        CONF_UNIT_SYSTEM: METRIC_SYSTEM.as_dict(),
        "location_name": "Home",
        "time_zone": "UTC",
        "components": set(),
        "config_dir": "/test/ha-config",
        "whitelist_external_dirs": set(),
        "allowlist_external_dirs": set(),
        "allowlist_external_urls": set(),
        "version": __version__,
        "config_source": "default",
        "safe_mode": False,
        "state": "RUNNING",
        "external_url": None,
        "internal_url": None,
    }

    assert expected == config.as_dict()


def test_config_is_allowed_path():
    """Test is_allowed_path method."""
    config = ha.Config(None)
    with TemporaryDirectory() as tmp_dir:
        # The created dir is in /tmp. This is a symlink on OS X
        # causing this test to fail unless we resolve path first.
        config.allowlist_external_dirs = {os.path.realpath(tmp_dir)}

        test_file = os.path.join(tmp_dir, "test.jpg")
        with open(test_file, "w") as tmp_file:
            tmp_file.write("test")

        valid = [test_file, tmp_dir, os.path.join(tmp_dir, "notfound321")]
        for path in valid:
            assert config.is_allowed_path(path)

        config.allowlist_external_dirs = {"/home", "/var"}

        invalid = [
            "/hass/config/secure",
            "/etc/passwd",
            "/root/secure_file",
            "/var/../etc/passwd",
            test_file,
        ]
        for path in invalid:
            assert not config.is_allowed_path(path)

        with pytest.raises(AssertionError):
            config.is_allowed_path(None)


def test_config_is_allowed_external_url():
    """Test is_allowed_external_url method."""
    config = ha.Config(None)
    config.allowlist_external_urls = [
        "http://x.com/",
        "https://y.com/bla/",
        "https://z.com/images/1.jpg/",
    ]

    valid = [
        "http://x.com/1.jpg",
        "http://x.com",
        "https://y.com/bla/",
        "https://y.com/bla/2.png",
        "https://z.com/images/1.jpg",
    ]
    for url in valid:
        assert config.is_allowed_external_url(url)

    invalid = [
        "https://a.co",
        "https://y.com/bla_wrong",
        "https://y.com/bla/../image.jpg",
        "https://z.com/images",
    ]
    for url in invalid:
        assert not config.is_allowed_external_url(url)


async def test_event_on_update(hass):
    """Test that event is fired on update."""
    events = []

    @ha.callback
    def callback(event):
        events.append(event)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, callback)

    assert hass.config.latitude != 12

    await hass.config.async_update(latitude=12)
    await hass.async_block_till_done()

    assert hass.config.latitude == 12
    assert len(events) == 1
    assert events[0].data == {"latitude": 12}


async def test_bad_timezone_raises_value_error(hass):
    """Test bad timezone raises ValueError."""
    with pytest.raises(ValueError):
        await hass.config.async_update(time_zone="not_a_timezone")


@patch("homeassistant.core.monotonic")
def test_create_timer(mock_monotonic, loop):
    """Test create timer."""
    hass = MagicMock()
    funcs = []
    orig_callback = ha.callback

    def mock_callback(func):
        funcs.append(func)
        return orig_callback(func)

    mock_monotonic.side_effect = 10.2, 10.8, 11.3

    with patch.object(ha, "callback", mock_callback), patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 5, 333333),
    ):
        ha._async_create_timer(hass)

    assert len(funcs) == 2
    fire_time_event, stop_timer = funcs

    assert len(hass.loop.call_later.mock_calls) == 1
    delay, callback, target = hass.loop.call_later.mock_calls[0][1]
    assert abs(delay - 0.666667) < 0.001
    assert callback is fire_time_event
    assert abs(target - 10.866667) < 0.001

    with patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 6, 100000),
    ):
        callback(target)

    assert len(hass.bus.async_listen_once.mock_calls) == 1
    assert len(hass.bus.async_fire.mock_calls) == 1
    assert len(hass.loop.call_later.mock_calls) == 2

    event_type, callback = hass.bus.async_listen_once.mock_calls[0][1]
    assert event_type == EVENT_HOMEASSISTANT_STOP
    assert callback is stop_timer

    delay, callback, target = hass.loop.call_later.mock_calls[1][1]
    assert abs(delay - 0.9) < 0.001
    assert callback is fire_time_event
    assert abs(target - 12.2) < 0.001

    event_type, event_data = hass.bus.async_fire.mock_calls[0][1]
    assert event_type == EVENT_TIME_CHANGED
    assert event_data[ATTR_NOW] == datetime(2018, 12, 31, 3, 4, 6, 100000)


@patch("homeassistant.core.monotonic")
def test_timer_out_of_sync(mock_monotonic, loop):
    """Test create timer."""
    hass = MagicMock()
    funcs = []
    orig_callback = ha.callback

    def mock_callback(func):
        funcs.append(func)
        return orig_callback(func)

    mock_monotonic.side_effect = 10.2, 13.3, 13.4

    with patch.object(ha, "callback", mock_callback), patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 5, 333333),
    ):
        ha._async_create_timer(hass)

    delay, callback, target = hass.loop.call_later.mock_calls[0][1]

    with patch(
        "homeassistant.core.dt_util.utcnow",
        return_value=datetime(2018, 12, 31, 3, 4, 8, 200000),
    ):
        callback(target)

        _, event_0_args, event_0_kwargs = hass.bus.async_fire.mock_calls[0]
        event_context_0 = event_0_kwargs["context"]

        event_type_0, _ = event_0_args
        assert event_type_0 == EVENT_TIME_CHANGED

        _, event_1_args, event_1_kwargs = hass.bus.async_fire.mock_calls[1]
        event_type_1, event_data_1 = event_1_args
        event_context_1 = event_1_kwargs["context"]

        assert event_type_1 == EVENT_TIMER_OUT_OF_SYNC
        assert abs(event_data_1[ATTR_SECONDS] - 2.433333) < 0.001

        assert event_context_0 == event_context_1

        assert len(funcs) == 2
        fire_time_event, _ = funcs

    assert len(hass.loop.call_later.mock_calls) == 2

    delay, callback, target = hass.loop.call_later.mock_calls[1][1]
    assert abs(delay - 0.8) < 0.001
    assert callback is fire_time_event
    assert abs(target - 14.2) < 0.001


async def test_hass_start_starts_the_timer(loop):
    """Test when hass starts, it starts the timer."""
    hass = ha.HomeAssistant()

    try:
        with patch("homeassistant.core._async_create_timer") as mock_timer:
            await hass.async_start()

        assert hass.state == ha.CoreState.running
        assert not hass._track_task
        assert len(mock_timer.mock_calls) == 1
        assert mock_timer.mock_calls[0][1][0] is hass

    finally:
        await hass.async_stop()
        assert hass.state == ha.CoreState.stopped


async def test_start_taking_too_long(loop, caplog):
    """Test when async_start takes too long."""
    hass = ha.HomeAssistant()
    caplog.set_level(logging.WARNING)

    try:
        with patch.object(
            hass, "async_block_till_done", side_effect=asyncio.TimeoutError
        ), patch("homeassistant.core._async_create_timer") as mock_timer:
            await hass.async_start()

        assert hass.state == ha.CoreState.running
        assert len(mock_timer.mock_calls) == 1
        assert mock_timer.mock_calls[0][1][0] is hass
        assert "Something is blocking Home Assistant" in caplog.text

    finally:
        await hass.async_stop()
        assert hass.state == ha.CoreState.stopped


async def test_track_task_functions(loop):
    """Test function to start/stop track task and initial state."""
    hass = ha.HomeAssistant()
    try:
        assert hass._track_task

        hass.async_stop_track_tasks()
        assert not hass._track_task

        hass.async_track_tasks()
        assert hass._track_task
    finally:
        await hass.async_stop()


async def test_service_executed_with_subservices(hass):
    """Test we block correctly till all services done."""
    calls = async_mock_service(hass, "test", "inner")
    context = ha.Context()

    async def handle_outer(call):
        """Handle outer service call."""
        calls.append(call)
        call1 = hass.services.async_call(
            "test", "inner", blocking=True, context=call.context
        )
        call2 = hass.services.async_call(
            "test", "inner", blocking=True, context=call.context
        )
        await asyncio.wait([call1, call2])
        calls.append(call)

    hass.services.async_register("test", "outer", handle_outer)

    await hass.services.async_call("test", "outer", blocking=True, context=context)

    assert len(calls) == 4
    assert [call.service for call in calls] == ["outer", "inner", "inner", "outer"]
    assert all(call.context is context for call in calls)


async def test_service_call_event_contains_original_data(hass):
    """Test that service call event contains original data."""
    events = []

    @ha.callback
    def callback(event):
        events.append(event)

    hass.bus.async_listen(EVENT_CALL_SERVICE, callback)

    calls = async_mock_service(
        hass, "test", "service", vol.Schema({"number": vol.Coerce(int)})
    )

    context = ha.Context()
    await hass.services.async_call(
        "test", "service", {"number": "23"}, blocking=True, context=context
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["service_data"]["number"] == "23"
    assert events[0].context is context
    assert len(calls) == 1
    assert calls[0].data["number"] == 23
    assert calls[0].context is context


def test_context():
    """Test context init."""
    c = ha.Context()
    assert c.user_id is None
    assert c.parent_id is None
    assert c.id is not None

    c = ha.Context(23, 100)
    assert c.user_id == 23
    assert c.parent_id == 100
    assert c.id is not None


async def test_async_functions_with_callback(hass):
    """Test we deal with async functions accidentally marked as callback."""
    runs = []

    @ha.callback
    async def test():
        runs.append(True)

    await hass.async_add_job(test)
    assert len(runs) == 1

    hass.async_run_job(test)
    await hass.async_block_till_done()
    assert len(runs) == 2

    @ha.callback
    async def service_handler(call):
        runs.append(True)

    hass.services.async_register("test_domain", "test_service", service_handler)

    await hass.services.async_call("test_domain", "test_service", blocking=True)
    assert len(runs) == 3


@pytest.mark.parametrize("cancel_call", [True, False])
async def test_cancel_service_task(hass, cancel_call):
    """Test cancellation."""
    service_called = asyncio.Event()
    service_cancelled = False

    async def service_handler(call):
        nonlocal service_cancelled
        service_called.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            service_cancelled = True
            raise

    hass.services.async_register("test_domain", "test_service", service_handler)
    call_task = hass.async_create_task(
        hass.services.async_call("test_domain", "test_service", blocking=True)
    )

    tasks_1 = asyncio.all_tasks()
    await asyncio.wait_for(service_called.wait(), timeout=1)
    tasks_2 = asyncio.all_tasks() - tasks_1
    assert len(tasks_2) == 1
    service_task = tasks_2.pop()

    if cancel_call:
        call_task.cancel()
    else:
        service_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call_task

    assert service_cancelled


def test_valid_entity_id():
    """Test valid entity ID."""
    for invalid in [
        "_light.kitchen",
        ".kitchen",
        ".light.kitchen",
        "light_.kitchen",
        "light._kitchen",
        "light.",
        "light.kitchen__ceiling",
        "light.kitchen_yo_",
        "light.kitchen.",
        "Light.kitchen",
        "light.Kitchen",
        "lightkitchen",
    ]:
        assert not ha.valid_entity_id(invalid), invalid

    for valid in [
        "1.a",
        "1light.kitchen",
        "a.1",
        "a.a",
        "input_boolean.hello_world_0123",
        "light.1kitchen",
        "light.kitchen",
        "light.something_yoo",
    ]:
        assert ha.valid_entity_id(valid), valid


async def test_migration_base_url(hass, hass_storage):
    """Test that we migrate base url to internal/external url."""
    config = ha.Config(hass)
    stored = {"version": 1, "data": {}}
    hass_storage[ha.CORE_STORAGE_KEY] = stored
    with patch.object(hass.bus, "async_listen_once") as mock_listen:
        # Empty config
        await config.async_load()
        assert len(mock_listen.mock_calls) == 0

        # With just a name
        stored["data"] = {"location_name": "Test Name"}
        await config.async_load()
        assert len(mock_listen.mock_calls) == 1

        # With external url
        stored["data"]["external_url"] = "https://example.com"
        await config.async_load()
        assert len(mock_listen.mock_calls) == 1

    # Test that the event listener works
    assert mock_listen.mock_calls[0][1][0] == EVENT_HOMEASSISTANT_START

    # External
    hass.config.api = Mock(deprecated_base_url="https://loaded-example.com")
    await mock_listen.mock_calls[0][1][1](None)
    assert config.external_url == "https://loaded-example.com"

    # Internal
    for internal in ("http://hass.local", "http://192.168.1.100:8123"):
        hass.config.api = Mock(deprecated_base_url=internal)
        await mock_listen.mock_calls[0][1][1](None)
        assert config.internal_url == internal


async def test_additional_data_in_core_config(hass, hass_storage):
    """Test that we can handle additional data in core configuration."""
    config = ha.Config(hass)
    hass_storage[ha.CORE_STORAGE_KEY] = {
        "version": 1,
        "data": {"location_name": "Test Name", "additional_valid_key": "value"},
    }
    await config.async_load()
    assert config.location_name == "Test Name"


async def test_start_events(hass):
    """Test events fired when starting Home Assistant."""
    hass.state = ha.CoreState.not_running

    all_events = []

    @ha.callback
    def capture_events(ev):
        all_events.append(ev.event_type)

    hass.bus.async_listen(MATCH_ALL, capture_events)

    core_states = []

    @ha.callback
    def capture_core_state(_):
        core_states.append(hass.state)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, capture_core_state)

    await hass.async_start()
    await hass.async_block_till_done()

    assert all_events == [
        EVENT_CORE_CONFIG_UPDATE,
        EVENT_HOMEASSISTANT_START,
        EVENT_CORE_CONFIG_UPDATE,
        EVENT_HOMEASSISTANT_STARTED,
    ]
    assert core_states == [ha.CoreState.starting, ha.CoreState.running]


async def test_log_blocking_events(hass, caplog):
    """Ensure we log which task is blocking startup when debug logging is on."""
    caplog.set_level(logging.DEBUG)

    async def _wait_a_bit_1():
        await asyncio.sleep(0.1)

    async def _wait_a_bit_2():
        await asyncio.sleep(0.1)

    hass.async_create_task(_wait_a_bit_1())
    await hass.async_block_till_done()

    with patch.object(ha, "BLOCK_LOG_TIMEOUT", 0.0001):
        hass.async_create_task(_wait_a_bit_2())
        await hass.async_block_till_done()

    assert "_wait_a_bit_2" in caplog.text
    assert "_wait_a_bit_1" not in caplog.text


async def test_chained_logging_hits_log_timeout(hass, caplog):
    """Ensure we log which task is blocking startup when there is a task chain and debug logging is on."""
    caplog.set_level(logging.DEBUG)

    created = 0

    async def _task_chain_1():
        nonlocal created
        created += 1
        if created > 1000:
            return
        hass.async_create_task(_task_chain_2())

    async def _task_chain_2():
        nonlocal created
        created += 1
        if created > 1000:
            return
        hass.async_create_task(_task_chain_1())

    with patch.object(ha, "BLOCK_LOG_TIMEOUT", 0.0001):
        hass.async_create_task(_task_chain_1())
        await hass.async_block_till_done()

    assert "_task_chain_" in caplog.text


async def test_chained_logging_misses_log_timeout(hass, caplog):
    """Ensure we do not log which task is blocking startup if we do not hit the timeout."""
    caplog.set_level(logging.DEBUG)

    created = 0

    async def _task_chain_1():
        nonlocal created
        created += 1
        if created > 10:
            return
        hass.async_create_task(_task_chain_2())

    async def _task_chain_2():
        nonlocal created
        created += 1
        if created > 10:
            return
        hass.async_create_task(_task_chain_1())

    hass.async_create_task(_task_chain_1())
    await hass.async_block_till_done()

    assert "_task_chain_" not in caplog.text


async def test_async_all(hass):
    """Test async_all."""

    hass.states.async_set("switch.link", "on")
    hass.states.async_set("light.bowl", "on")
    hass.states.async_set("light.frog", "on")
    hass.states.async_set("vacuum.floor", "on")

    assert {state.entity_id for state in hass.states.async_all()} == {
        "switch.link",
        "light.bowl",
        "light.frog",
        "vacuum.floor",
    }
    assert {state.entity_id for state in hass.states.async_all("light")} == {
        "light.bowl",
        "light.frog",
    }
    assert {
        state.entity_id for state in hass.states.async_all(["light", "switch"])
    } == {"light.bowl", "light.frog", "switch.link"}


async def test_async_entity_ids_count(hass):
    """Test async_entity_ids_count."""

    hass.states.async_set("switch.link", "on")
    hass.states.async_set("light.bowl", "on")
    hass.states.async_set("light.frog", "on")
    hass.states.async_set("vacuum.floor", "on")

    assert hass.states.async_entity_ids_count() == 4
    assert hass.states.async_entity_ids_count("light") == 2

    hass.states.async_set("light.cow", "on")

    assert hass.states.async_entity_ids_count() == 5
    assert hass.states.async_entity_ids_count("light") == 3


async def test_hassjob_forbid_coroutine():
    """Test hassjob forbids coroutines."""

    async def bla():
        pass

    coro = bla()

    with pytest.raises(ValueError):
        ha.HassJob(coro)

    # To avoid warning about unawaited coro
    await coro


async def test_reserving_states(hass):
    """Test we can reserve a state in the state machine."""

    hass.states.async_reserve("light.bedroom")
    assert hass.states.async_available("light.bedroom") is False
    hass.states.async_set("light.bedroom", "on")
    assert hass.states.async_available("light.bedroom") is False

    with pytest.raises(ha.HomeAssistantError):
        hass.states.async_reserve("light.bedroom")

    hass.states.async_remove("light.bedroom")
    assert hass.states.async_available("light.bedroom") is True
    hass.states.async_set("light.bedroom", "on")

    with pytest.raises(ha.HomeAssistantError):
        hass.states.async_reserve("light.bedroom")

    assert hass.states.async_available("light.bedroom") is False
    hass.states.async_remove("light.bedroom")
    assert hass.states.async_available("light.bedroom") is True


async def test_state_change_events_match_state_time(hass):
    """Test last_updated and timed_fired only call utcnow once."""

    events = []

    @ha.callback
    def _event_listener(event):
        events.append(event)

    hass.bus.async_listen(ha.EVENT_STATE_CHANGED, _event_listener)

    hass.states.async_set("light.bedroom", "on")
    await hass.async_block_till_done()
    state = hass.states.get("light.bedroom")

    assert state.last_updated == events[0].time_fired
