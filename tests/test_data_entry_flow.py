"""Test the flow classes."""

import asyncio
import dataclasses
import logging
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.decorator import Registry

from .common import (
    async_capture_events,
    help_test_all,
    import_and_test_deprecated_constant_enum,
)


@pytest.fixture
def manager():
    """Return a flow manager."""
    handlers = Registry()
    entries = []

    class FlowManager(data_entry_flow.FlowManager):
        """Test flow manager."""

        async def async_create_flow(self, handler_key, *, context, data):
            """Test create flow."""
            handler = handlers.get(handler_key)

            if handler is None:
                raise data_entry_flow.UnknownHandler

            flow = handler()
            flow.init_step = context.get("init_step", "init")
            return flow

        async def async_finish_flow(self, flow, result):
            """Test finish flow."""
            if result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY:
                result["source"] = flow.context.get("source")
                entries.append(result)
            return result

    mgr = FlowManager(None)
    mgr.mock_created_entries = entries
    mgr.mock_reg_handler = handlers.register
    return mgr


async def test_configure_reuses_handler_instance(manager) -> None:
    """Test that we reuse instances."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        handle_count = 0

        async def async_step_init(self, user_input=None):
            self.handle_count += 1
            return self.async_show_form(
                errors={"base": str(self.handle_count)}, step_id="init"
            )

    form = await manager.async_init("test")
    assert form["errors"]["base"] == "1"
    form = await manager.async_configure(form["flow_id"])
    assert form["errors"]["base"] == "2"
    assert manager.async_progress() == [
        {
            "flow_id": form["flow_id"],
            "handler": "test",
            "step_id": "init",
            "context": {},
        }
    ]
    assert len(manager.mock_created_entries) == 0


async def test_configure_two_steps(manager: data_entry_flow.FlowManager) -> None:
    """Test that we reuse instances."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 1

        async def async_step_first(self, user_input=None):
            if user_input is not None:
                return await self.async_step_second()
            return self.async_show_form(step_id="first", data_schema=vol.Schema([str]))

        async def async_step_second(self, user_input=None):
            if user_input is not None:
                return self.async_create_entry(
                    title="Test Entry", data=self.init_data + user_input
                )
            return self.async_show_form(step_id="second", data_schema=vol.Schema([str]))

    form = await manager.async_init(
        "test", context={"init_step": "first"}, data=["INIT-DATA"]
    )

    with pytest.raises(vol.Invalid):
        form = await manager.async_configure(form["flow_id"], "INCORRECT-DATA")

    form = await manager.async_configure(form["flow_id"], ["SECOND-DATA"])
    assert form["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 1
    result = manager.mock_created_entries[0]
    assert result["handler"] == "test"
    assert result["data"] == ["INIT-DATA", "SECOND-DATA"]


async def test_show_form(manager) -> None:
    """Test that we can show a form."""
    schema = vol.Schema({vol.Required("username"): str, vol.Required("password"): str})

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        async def async_step_init(self, user_input=None):
            return self.async_show_form(
                step_id="init",
                data_schema=schema,
                errors={"username": "Should be unique."},
            )

    form = await manager.async_init("test")
    assert form["type"] == data_entry_flow.FlowResultType.FORM
    assert form["data_schema"] is schema
    assert form["errors"] == {"username": "Should be unique."}


async def test_abort_removes_instance(manager) -> None:
    """Test that abort removes the flow from progress."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        is_new = True

        async def async_step_init(self, user_input=None):
            old = self.is_new
            self.is_new = False
            return self.async_abort(reason=str(old))

    form = await manager.async_init("test")
    assert form["reason"] == "True"
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 0
    form = await manager.async_init("test")
    assert form["reason"] == "True"
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 0


async def test_abort_calls_async_remove(manager) -> None:
    """Test abort calling the async_remove FlowHandler method."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        async def async_step_init(self, user_input=None):
            return self.async_abort(reason="reason")

        async_remove = Mock()

    await manager.async_init("test")

    TestFlow.async_remove.assert_called_once()

    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 0


async def test_abort_calls_async_remove_with_exception(
    manager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test abort calling the async_remove FlowHandler method, with an exception."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        async def async_step_init(self, user_input=None):
            return self.async_abort(reason="reason")

        async_remove = Mock(side_effect=[RuntimeError("error")])

    with caplog.at_level(logging.ERROR):
        await manager.async_init("test")

    assert "Error removing test flow" in caplog.text

    TestFlow.async_remove.assert_called_once()

    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 0


async def test_create_saves_data(manager) -> None:
    """Test creating a config entry."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_create_entry(title="Test Title", data="Test Data")

    await manager.async_init("test")
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 1

    entry = manager.mock_created_entries[0]
    assert entry["handler"] == "test"
    assert entry["title"] == "Test Title"
    assert entry["data"] == "Test Data"
    assert entry["source"] is None


async def test_discovery_init_flow(manager) -> None:
    """Test a flow initialized by discovery."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5

        async def async_step_init(self, info):
            return self.async_create_entry(title=info["id"], data=info)

    data = {"id": "hello", "token": "secret"}

    await manager.async_init(
        "test", context={"source": config_entries.SOURCE_DISCOVERY}, data=data
    )
    assert len(manager.async_progress()) == 0
    assert len(manager.mock_created_entries) == 1

    entry = manager.mock_created_entries[0]
    assert entry["handler"] == "test"
    assert entry["title"] == "hello"
    assert entry["data"] == data
    assert entry["source"] == config_entries.SOURCE_DISCOVERY


async def test_finish_callback_change_result_type(hass: HomeAssistant) -> None:
    """Test finish callback can change result type."""

    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 1

        async def async_step_init(self, input):
            """Return init form with one input field 'count'."""
            if input is not None:
                return self.async_create_entry(title="init", data=input)
            return self.async_show_form(
                step_id="init", data_schema=vol.Schema({"count": int})
            )

    class FlowManager(data_entry_flow.FlowManager):
        async def async_create_flow(self, handler_name, *, context, data):
            """Create a test flow."""
            return TestFlow()

        async def async_finish_flow(self, flow, result):
            """Redirect to init form if count <= 1."""
            if result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY:
                if result["data"] is None or result["data"].get("count", 0) <= 1:
                    return flow.async_show_form(
                        step_id="init", data_schema=vol.Schema({"count": int})
                    )
                result["result"] = result["data"]["count"]
            return result

    manager = FlowManager(hass)

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await manager.async_configure(result["flow_id"], {"count": 0})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "result" not in result

    result = await manager.async_configure(result["flow_id"], {"count": 2})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"] == 2


async def test_external_step(hass: HomeAssistant, manager) -> None:
    """Test external step logic."""
    manager.hass = hass

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None

        async def async_step_init(self, user_input=None):
            if not user_input:
                return self.async_external_step(
                    step_id="init", url="https://example.com"
                )

            self.data = user_input
            return self.async_external_step_done(next_step_id="finish")

        async def async_step_finish(self, user_input=None):
            return self.async_create_entry(title=self.data["title"], data=self.data)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESSED
    )

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    # Mimic external step
    # Called by integrations: `hass.config_entries.flow.async_configure(…)`
    result = await manager.async_configure(result["flow_id"], {"title": "Hello"})
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE

    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == {
        "handler": "test",
        "flow_id": result["flow_id"],
        "refresh": True,
    }

    # Frontend refreshes the flow
    result = await manager.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hello"


async def test_show_progress(hass: HomeAssistant, manager) -> None:
    """Test show progress logic."""
    manager.hass = hass
    events = []
    task_one_evt = asyncio.Event()
    task_two_evt = asyncio.Event()
    event_received_evt = asyncio.Event()

    @callback
    def capture_events(event: Event) -> None:
        events.append(event)
        event_received_evt.set()

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None
        start_task_two = False
        task_one: asyncio.Task[None] | None = None
        task_two: asyncio.Task[None] | None = None

        async def async_step_init(self, user_input=None):
            async def long_running_job_one() -> None:
                await task_one_evt.wait()

            async def long_running_job_two() -> None:
                await task_two_evt.wait()
                self.data = {"title": "Hello"}

            uncompleted_task: asyncio.Task[None] | None = None
            if not self.task_one:
                self.task_one = hass.async_create_task(long_running_job_one())

            progress_action = None
            if not self.task_one.done():
                progress_action = "task_one"
                uncompleted_task = self.task_one

            if not uncompleted_task:
                if not self.task_two:
                    self.task_two = hass.async_create_task(long_running_job_two())

                if not self.task_two.done():
                    progress_action = "task_two"
                    uncompleted_task = self.task_two

            if uncompleted_task:
                assert progress_action
                return self.async_show_progress(
                    progress_action=progress_action,
                    progress_task=uncompleted_task,
                )

            return self.async_show_progress_done(next_step_id="finish")

        async def async_step_finish(self, user_input=None):
            return self.async_create_entry(title=self.data["title"], data=self.data)

    hass.bus.async_listen(
        data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESSED,
        capture_events,
    )

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_one"
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    # Set task one done and wait for event
    task_one_evt.set()
    await event_received_evt.wait()
    event_received_evt.clear()
    assert len(events) == 1
    assert events[0].data == {
        "handler": "test",
        "flow_id": result["flow_id"],
        "refresh": True,
    }

    # Frontend refreshes the flow
    result = await manager.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_two"

    # Set task two done and wait for event
    task_two_evt.set()
    await event_received_evt.wait()
    event_received_evt.clear()
    assert len(events) == 2  # 1 for task one and 1 for task two
    assert events[1].data == {
        "handler": "test",
        "flow_id": result["flow_id"],
        "refresh": True,
    }

    # Frontend refreshes the flow
    result = await manager.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hello"


async def test_show_progress_error(hass: HomeAssistant, manager) -> None:
    """Test show progress logic."""
    manager.hass = hass
    events = []
    event_received_evt = asyncio.Event()

    @callback
    def capture_events(event: Event) -> None:
        events.append(event)
        event_received_evt.set()

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None
        progress_task: asyncio.Task[None] | None = None

        async def async_step_init(self, user_input=None):
            async def long_running_task() -> None:
                await asyncio.sleep(0)
                raise TypeError

            if not self.progress_task:
                self.progress_task = hass.async_create_task(long_running_task())
            if self.progress_task and self.progress_task.done():
                if self.progress_task.exception():
                    return self.async_show_progress_done(next_step_id="error")
                return self.async_show_progress_done(next_step_id="no_error")
            return self.async_show_progress(
                progress_action="task", progress_task=self.progress_task
            )

        async def async_step_error(self, user_input=None):
            return self.async_abort(reason="error")

    hass.bus.async_listen(
        data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESSED,
        capture_events,
    )

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task"
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    # Set task one done and wait for event
    await event_received_evt.wait()
    event_received_evt.clear()
    assert len(events) == 1
    assert events[0].data == {
        "handler": "test",
        "flow_id": result["flow_id"],
        "refresh": True,
    }

    # Frontend refreshes the flow
    result = await manager.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "error"


async def test_show_progress_hidden_from_frontend(hass: HomeAssistant, manager) -> None:
    """Test show progress done is not sent to frontend."""
    manager.hass = hass
    async_show_progress_done_called = False
    progress_task: asyncio.Task[None] | None = None

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None

        async def async_step_init(self, user_input=None):
            nonlocal progress_task

            async def long_running_job() -> None:
                await asyncio.sleep(0)

            if not progress_task:
                progress_task = hass.async_create_task(long_running_job())
            if progress_task.done():
                nonlocal async_show_progress_done_called
                async_show_progress_done_called = True
                return self.async_show_progress_done(next_step_id="finish")
            return self.async_show_progress(
                step_id="init",
                progress_action="task",
                # Set to a task which never finishes to simulate flow manager has not
                # yet called when frontend loads
                progress_task=hass.async_create_task(asyncio.Event().wait()),
            )

        async def async_step_finish(self, user_input=None):
            return self.async_create_entry(title=None, data=self.data)

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task"
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    await progress_task
    assert not async_show_progress_done_called

    # Frontend refreshes the flow
    result = await manager.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert async_show_progress_done_called


async def test_show_progress_legacy(hass: HomeAssistant, manager, caplog) -> None:
    """Test show progress logic.

    This tests the deprecated version where the config flow is responsible for
    resuming the flow.
    """
    manager.hass = hass

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None
        task_one_done = False
        task_two_done = False

        async def async_step_init(self, user_input=None):
            if user_input and "task_finished" in user_input:
                if user_input["task_finished"] == 1:
                    self.task_one_done = True
                elif user_input["task_finished"] == 2:
                    self.task_two_done = True

            if not self.task_one_done:
                progress_action = "task_one"
            elif not self.task_two_done:
                progress_action = "task_two"
            if not self.task_one_done or not self.task_two_done:
                return self.async_show_progress(
                    step_id="init",
                    progress_action=progress_action,
                )

            self.data = user_input
            return self.async_show_progress_done(next_step_id="finish")

        async def async_step_finish(self, user_input=None):
            return self.async_create_entry(title=self.data["title"], data=self.data)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESSED
    )

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_one"
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    # Mimic task one done and moving to task two
    # Called by integrations: `hass.config_entries.flow.async_configure(…)`
    result = await manager.async_configure(result["flow_id"], {"task_finished": 1})
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_two"

    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == {
        "handler": "test",
        "flow_id": result["flow_id"],
        "refresh": True,
    }

    # Frontend refreshes the flow
    result = await manager.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_two"

    # Mimic task two done and continuing step
    # Called by integrations: `hass.config_entries.flow.async_configure(…)`
    result = await manager.async_configure(
        result["flow_id"], {"task_finished": 2, "title": "Hello"}
    )
    # Note: The SHOW_PROGRESS_DONE is not hidden from frontend when flows manage
    # the progress tasks themselves
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS_DONE

    # Frontend refreshes the flow
    result = await manager.async_configure(
        result["flow_id"], {"task_finished": 2, "title": "Hello"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hello"

    await hass.async_block_till_done()
    assert len(events) == 2  # 1 for task one and 1 for task two
    assert events[1].data == {
        "handler": "test",
        "flow_id": result["flow_id"],
        "refresh": True,
    }

    # Check for deprecation warning
    assert (
        "tests.test_data_entry_flow::TestFlow calls async_show_progress without passing"
        " a progress task, this is not valid and will break in Home Assistant "
        "Core 2024.8."
    ) in caplog.text


async def test_show_progress_fires_only_when_changed(
    hass: HomeAssistant, manager
) -> None:
    """Test show progress change logic."""
    manager.hass = hass

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None

        async def async_step_init(self, user_input=None):
            if user_input:
                progress_action = user_input["progress_action"]
                description_placeholders = user_input["description_placeholders"]
                return self.async_show_progress(
                    step_id="init",
                    progress_action=progress_action,
                    description_placeholders=description_placeholders,
                )
            return self.async_show_progress(step_id="init", progress_action="task_one")

        async def async_step_finish(self, user_input=None):
            return self.async_create_entry(title=self.data["title"], data=self.data)

    events = async_capture_events(
        hass, data_entry_flow.EVENT_DATA_ENTRY_FLOW_PROGRESSED
    )

    async def test_change(
        flow_id,
        events,
        progress_action,
        description_placeholders_progress,
        number_of_events,
        is_change,
    ) -> None:
        # Called by integrations: `hass.config_entries.flow.async_configure(…)`
        result = await manager.async_configure(
            flow_id,
            {
                "progress_action": progress_action,
                "description_placeholders": {
                    "progress": description_placeholders_progress
                },
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == progress_action
        assert (
            result["description_placeholders"]["progress"]
            == description_placeholders_progress
        )

        await hass.async_block_till_done()
        assert len(events) == number_of_events
        if is_change:
            assert events[number_of_events - 1].data == {
                "handler": "test",
                "flow_id": result["flow_id"],
                "refresh": True,
            }

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_one"
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    # Mimic task one tests
    await test_change(
        result["flow_id"], events, "task_one", 0, 1, True
    )  # change (progress action)
    await test_change(result["flow_id"], events, "task_one", 0, 1, False)  # no change
    await test_change(
        result["flow_id"], events, "task_one", 25, 2, True
    )  # change (description placeholder)
    await test_change(
        result["flow_id"], events, "task_two", 50, 3, True
    )  # change (progress action and description placeholder)
    await test_change(result["flow_id"], events, "task_two", 50, 3, False)  # no change
    await test_change(
        result["flow_id"], events, "task_two", 100, 4, True
    )  # change (description placeholder)


async def test_abort_flow_exception(manager) -> None:
    """Test that the AbortFlow exception works."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        async def async_step_init(self, user_input=None):
            raise data_entry_flow.AbortFlow("mock-reason", {"placeholder": "yo"})

    form = await manager.async_init("test")
    assert form["type"] == data_entry_flow.FlowResultType.ABORT
    assert form["reason"] == "mock-reason"
    assert form["description_placeholders"] == {"placeholder": "yo"}


async def test_init_unknown_flow(manager) -> None:
    """Test that UnknownFlow is raised when async_create_flow returns None."""

    with (
        pytest.raises(data_entry_flow.UnknownFlow),
        patch.object(manager, "async_create_flow", return_value=None),
    ):
        await manager.async_init("test")


async def test_async_get_unknown_flow(manager) -> None:
    """Test that UnknownFlow is raised when async_get is called with a flow_id that does not exist."""

    with pytest.raises(data_entry_flow.UnknownFlow):
        await manager.async_get("does_not_exist")


async def test_async_has_matching_flow(
    hass: HomeAssistant, manager: data_entry_flow.FlowManager
) -> None:
    """Test we can check for matching flows."""
    manager.hass = hass
    assert (
        manager.async_has_matching_flow(
            "test",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is False
    )

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_show_progress(
                step_id="init",
                progress_action="task_one",
            )

    result = await manager.async_init(
        "test",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
    )
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_one"
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert (
        len(
            manager.async_progress_by_handler(
                "test", match_context={"source": config_entries.SOURCE_HOMEKIT}
            )
        )
        == 1
    )
    assert (
        len(
            manager.async_progress_by_handler(
                "test", match_context={"source": config_entries.SOURCE_BLUETOOTH}
            )
        )
        == 0
    )
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    assert (
        manager.async_has_matching_flow(
            "test",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is True
    )
    assert (
        manager.async_has_matching_flow(
            "test",
            {"source": config_entries.SOURCE_SSDP},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is False
    )
    assert (
        manager.async_has_matching_flow(
            "other",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is False
    )


async def test_move_to_unknown_step_raises_and_removes_from_in_progress(
    manager,
) -> None:
    """Test that moving to an unknown step raises and removes the flow from in progress."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 1

    with pytest.raises(data_entry_flow.UnknownStep):
        await manager.async_init("test", context={"init_step": "does_not_exist"})

    assert manager.async_progress() == []


@pytest.mark.parametrize(
    ("result_type", "params"),
    [
        ("async_external_step_done", {"next_step_id": "does_not_exist"}),
        ("async_external_step", {"step_id": "does_not_exist", "url": "blah"}),
        ("async_show_form", {"step_id": "does_not_exist"}),
        ("async_show_menu", {"step_id": "does_not_exist", "menu_options": []}),
        ("async_show_progress_done", {"next_step_id": "does_not_exist"}),
        ("async_show_progress", {"step_id": "does_not_exist", "progress_action": ""}),
    ],
)
async def test_next_step_unknown_step_raises_and_removes_from_in_progress(
    manager, result_type: str, params: dict[str, str]
) -> None:
    """Test that moving to an unknown step raises and removes the flow from in progress."""

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 1

        async def async_step_init(self, user_input=None):
            return getattr(self, result_type)(**params)

    with pytest.raises(data_entry_flow.UnknownStep):
        await manager.async_init("test", context={"init_step": "init"})

    assert manager.async_progress() == []


async def test_configure_raises_unknown_flow_if_not_in_progress(manager) -> None:
    """Test configure raises UnknownFlow if the flow is not in progress."""
    with pytest.raises(data_entry_flow.UnknownFlow):
        await manager.async_configure("wrong_flow_id")


async def test_abort_raises_unknown_flow_if_not_in_progress(manager) -> None:
    """Test abort raises UnknownFlow if the flow is not in progress."""
    with pytest.raises(data_entry_flow.UnknownFlow):
        await manager.async_abort("wrong_flow_id")


@pytest.mark.parametrize(
    "menu_options",
    [["target1", "target2"], {"target1": "Target 1", "target2": "Target 2"}],
)
async def test_show_menu(hass: HomeAssistant, manager, menu_options) -> None:
    """Test show menu."""
    manager.hass = hass

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 5
        data = None
        task_one_done = False

        async def async_step_init(self, user_input=None):
            return self.async_show_menu(
                step_id="init",
                menu_options=menu_options,
                description_placeholders={"name": "Paulus"},
            )

        async def async_step_target1(self, user_input=None):
            return self.async_show_form(step_id="target1")

        async def async_step_target2(self, user_input=None):
            return self.async_show_form(step_id="target2")

    result = await manager.async_init("test")
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["menu_options"] == menu_options
    assert result["description_placeholders"] == {"name": "Paulus"}
    assert len(manager.async_progress()) == 1
    assert len(manager.async_progress_by_handler("test")) == 1
    assert manager.async_get(result["flow_id"])["handler"] == "test"

    # Mimic picking a step
    result = await manager.async_configure(
        result["flow_id"], {"next_step_id": "target1"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "target1"


async def test_find_flows_by_init_data_type(
    manager: data_entry_flow.FlowManager,
) -> None:
    """Test we can find flows by init data type."""

    @dataclasses.dataclass
    class BluetoothDiscoveryData:
        """Bluetooth Discovery data."""

        address: str

    @dataclasses.dataclass
    class WiFiDiscoveryData:
        """WiFi Discovery data."""

        address: str

    @manager.mock_reg_handler("test")
    class TestFlow(data_entry_flow.FlowHandler):
        VERSION = 1

        async def async_step_first(self, user_input=None):
            if user_input is not None:
                return await self.async_step_second()
            return self.async_show_form(step_id="first", data_schema=vol.Schema([str]))

        async def async_step_second(self, user_input=None):
            if user_input is not None:
                return self.async_create_entry(
                    title="Test Entry",
                    data={"init": self.init_data, "user": user_input},
                )
            return self.async_show_form(step_id="second", data_schema=vol.Schema([str]))

    bluetooth_data = BluetoothDiscoveryData("aa:bb:cc:dd:ee:ff")
    wifi_data = WiFiDiscoveryData("host")

    bluetooth_form = await manager.async_init(
        "test", context={"init_step": "first"}, data=bluetooth_data
    )
    await manager.async_init("test", context={"init_step": "first"}, data=wifi_data)

    assert (
        len(
            manager.async_progress_by_init_data_type(
                BluetoothDiscoveryData, lambda data: True
            )
        )
    ) == 1
    assert (
        len(
            manager.async_progress_by_init_data_type(
                BluetoothDiscoveryData,
                lambda data: bool(data.address == "aa:bb:cc:dd:ee:ff"),
            )
        )
    ) == 1
    assert (
        len(
            manager.async_progress_by_init_data_type(
                BluetoothDiscoveryData, lambda data: bool(data.address == "not it")
            )
        )
    ) == 0

    wifi_flows = manager.async_progress_by_init_data_type(
        WiFiDiscoveryData, lambda data: True
    )
    assert len(wifi_flows) == 1

    bluetooth_result = await manager.async_configure(
        bluetooth_form["flow_id"], ["SECOND-DATA"]
    )
    assert bluetooth_result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(manager.async_progress()) == 1
    assert len(manager.mock_created_entries) == 1
    result = manager.mock_created_entries[0]
    assert result["handler"] == "test"
    assert result["data"] == {"init": bluetooth_data, "user": ["SECOND-DATA"]}

    bluetooth_flows = manager.async_progress_by_init_data_type(
        BluetoothDiscoveryData, lambda data: True
    )
    assert len(bluetooth_flows) == 0

    wifi_flows = manager.async_progress_by_init_data_type(
        WiFiDiscoveryData, lambda data: True
    )
    assert len(wifi_flows) == 1

    manager.async_abort(wifi_flows[0]["flow_id"])

    wifi_flows = manager.async_progress_by_init_data_type(
        WiFiDiscoveryData, lambda data: True
    )
    assert len(wifi_flows) == 0
    assert len(manager.async_progress()) == 0


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(data_entry_flow)


@pytest.mark.parametrize(("enum"), list(data_entry_flow.FlowResultType))
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: data_entry_flow.FlowResultType,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(
        caplog, data_entry_flow, enum, "RESULT_TYPE_", "2025.1"
    )
