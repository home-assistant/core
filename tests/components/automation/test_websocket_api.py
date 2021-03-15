"""Test Automation config panel."""
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import automation, config
from homeassistant.core import Context

from tests.common import assert_lists_same
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


def _find_run_id(traces, automation_id):
    """Find newest run_id for an automation."""
    for trace in reversed(traces):
        if trace["automation_id"] == automation_id:
            return trace["run_id"]

    return None


def _find_traces_for_automation(traces, automation_id):
    """Find traces for an automation."""
    return [trace for trace in traces if trace["automation_id"] == automation_id]


async def test_get_automation_trace(hass, hass_ws_client):
    """Test tracing an automation."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": {"service": "test.automation"},
    }
    moon_config = {
        "id": "moon",
        "trigger": [
            {"platform": "event", "event_type": "test_event2"},
            {"platform": "event", "event_type": "test_event3"},
        ],
        "condition": {
            "condition": "template",
            "value_template": "{{ trigger.event.event_type=='test_event2' }}",
        },
        "action": {"event": "another_event"},
    }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                sun_config,
                moon_config,
            ]
        },
    )

    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client()

    # Trigger "sun" automation
    context = Context()
    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "sun")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/trace/get",
            "automation_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert trace["context"]["parent_id"] == context.id
    assert len(trace["action_trace"]) == 1
    assert len(trace["action_trace"]["action/0"]) == 1
    assert trace["action_trace"]["action/0"][0]["error"]
    assert "result" not in trace["action_trace"]["action/0"][0]
    assert trace["condition_trace"] == {}
    assert trace["config"] == sun_config
    assert trace["context"]
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["trigger"] == "event 'test_event'"
    assert trace["unique_id"] == "sun"
    assert trace["variables"]

    # Trigger "moon" automation, with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "moon")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/trace/get",
            "automation_id": "moon",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert len(trace["action_trace"]) == 1
    assert len(trace["action_trace"]["action/0"]) == 1
    assert "error" not in trace["action_trace"]["action/0"][0]
    assert "result" not in trace["action_trace"]["action/0"][0]
    assert len(trace["condition_trace"]) == 1
    assert len(trace["condition_trace"]["condition/0"]) == 1
    assert trace["condition_trace"]["condition/0"][0]["result"] == {"result": True}
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["trigger"] == "event 'test_event2'"
    assert trace["unique_id"] == "moon"
    assert trace["variables"]

    # Trigger "moon" automation, with failing condition
    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "moon")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/trace/get",
            "automation_id": "moon",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert len(trace["action_trace"]) == 0
    assert len(trace["condition_trace"]) == 1
    assert len(trace["condition_trace"]["condition/0"]) == 1
    assert trace["condition_trace"]["condition/0"][0]["result"] == {"result": False}
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["trigger"] == "event 'test_event3'"
    assert trace["unique_id"] == "moon"
    assert trace["variables"]

    # Trigger "moon" automation, with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "moon")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/trace/get",
            "automation_id": "moon",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert len(trace["action_trace"]) == 1
    assert len(trace["action_trace"]["action/0"]) == 1
    assert "error" not in trace["action_trace"]["action/0"][0]
    assert "result" not in trace["action_trace"]["action/0"][0]
    assert len(trace["condition_trace"]) == 1
    assert len(trace["condition_trace"]["condition/0"]) == 1
    assert trace["condition_trace"]["condition/0"][0]["result"] == {"result": True}
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["trigger"] == "event 'test_event2'"
    assert trace["unique_id"] == "moon"
    assert trace["variables"]


async def test_automation_trace_overflow(hass, hass_ws_client):
    """Test the number of stored traces per automation is limited."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": {"event": "some_event"},
    }
    moon_config = {
        "id": "moon",
        "trigger": {"platform": "event", "event_type": "test_event2"},
        "action": {"event": "another_event"},
    }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                sun_config,
                moon_config,
            ]
        },
    )

    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client()

    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "sun" and "moon" automation once
    hass.bus.async_fire("test_event")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces_for_automation(response["result"], "moon")) == 1
    moon_run_id = _find_run_id(response["result"], "moon")
    assert len(_find_traces_for_automation(response["result"], "sun")) == 1

    # Trigger "moon" automation enough times to overflow the number of stored traces
    for _ in range(automation.trace.STORED_TRACES):
        hass.bus.async_fire("test_event2")
        await hass.async_block_till_done()

    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    moon_traces = _find_traces_for_automation(response["result"], "moon")
    assert len(moon_traces) == automation.trace.STORED_TRACES
    assert moon_traces[0]
    assert int(moon_traces[0]["run_id"]) == int(moon_run_id) + 1
    assert (
        int(moon_traces[-1]["run_id"])
        == int(moon_run_id) + automation.trace.STORED_TRACES
    )
    assert len(_find_traces_for_automation(response["result"], "sun")) == 1


async def test_list_automation_traces(hass, hass_ws_client):
    """Test listing automation traces."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": {"service": "test.automation"},
    }
    moon_config = {
        "id": "moon",
        "trigger": [
            {"platform": "event", "event_type": "test_event2"},
            {"platform": "event", "event_type": "test_event3"},
        ],
        "condition": {
            "condition": "template",
            "value_template": "{{ trigger.event.event_type=='test_event2' }}",
        },
        "action": {"event": "another_event"},
    }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                sun_config,
                moon_config,
            ]
        },
    )

    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client()

    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    await client.send_json(
        {"id": next_id(), "type": "automation/trace/list", "automation_id": "sun"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "sun" automation
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert len(_find_traces_for_automation(response["result"], "sun")) == 1

    await client.send_json(
        {"id": next_id(), "type": "automation/trace/list", "automation_id": "sun"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert len(_find_traces_for_automation(response["result"], "sun")) == 1

    await client.send_json(
        {"id": next_id(), "type": "automation/trace/list", "automation_id": "moon"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "moon" automation, with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # Trigger "moon" automation, with failing condition
    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()

    # Trigger "moon" automation, with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json({"id": next_id(), "type": "automation/trace/list"})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces_for_automation(response["result"], "moon")) == 3
    assert len(_find_traces_for_automation(response["result"], "sun")) == 1
    trace = _find_traces_for_automation(response["result"], "sun")[0]
    assert trace["last_action"] == "action/0"
    assert trace["last_condition"] is None
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["trigger"] == "event 'test_event'"
    assert trace["unique_id"] == "sun"

    trace = _find_traces_for_automation(response["result"], "moon")[0]
    assert trace["last_action"] == "action/0"
    assert trace["last_condition"] == "condition/0"
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["trigger"] == "event 'test_event2'"
    assert trace["unique_id"] == "moon"

    trace = _find_traces_for_automation(response["result"], "moon")[1]
    assert trace["last_action"] is None
    assert trace["last_condition"] == "condition/0"
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["trigger"] == "event 'test_event3'"
    assert trace["unique_id"] == "moon"

    trace = _find_traces_for_automation(response["result"], "moon")[2]
    assert trace["last_action"] == "action/0"
    assert trace["last_condition"] == "condition/0"
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["trigger"] == "event 'test_event2'"
    assert trace["unique_id"] == "moon"


async def test_automation_breakpoints(hass, hass_ws_client):
    """Test automation breakpoints."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_last_action(automation_id, expected_action, expected_state):
        await client.send_json({"id": next_id(), "type": "automation/trace/list"})
        response = await client.receive_json()
        assert response["success"]
        trace = _find_traces_for_automation(response["result"], automation_id)[-1]
        assert trace["last_action"] == expected_action
        assert trace["state"] == expected_state
        return trace["run_id"]

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": [
            {"event": "event0"},
            {"event": "event1"},
            {"event": "event2"},
            {"event": "event3"},
            {"event": "event4"},
            {"event": "event5"},
            {"event": "event6"},
            {"event": "event7"},
            {"event": "event8"},
        ],
    }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                sun_config,
            ]
        },
    )

    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client()

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "1",
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json(
        {"id": next_id(), "type": "automation/debug/breakpoint/list"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    subscription_id = next_id()
    await client.send_json(
        {"id": subscription_id, "type": "automation/debug/breakpoint/subscribe"}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "action/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "action/5",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {"id": next_id(), "type": "automation/debug/breakpoint/list"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert_lists_same(
        response["result"],
        [
            {"node": "action/1", "run_id": "*", "automation_id": "sun"},
            {"node": "action/5", "run_id": "*", "automation_id": "sun"},
        ],
    )

    # Trigger "sun" automation
    hass.bus.async_fire("test_event")

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/1", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/1",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/step",
            "automation_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/2", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/2",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/continue",
            "automation_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/5", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/5",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/stop",
            "automation_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await assert_last_action("sun", "action/5", "stopped")


async def test_automation_breakpoints_2(hass, hass_ws_client):
    """Test execution resumes and breakpoints are removed after subscription removed."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_last_action(automation_id, expected_action, expected_state):
        await client.send_json({"id": next_id(), "type": "automation/trace/list"})
        response = await client.receive_json()
        assert response["success"]
        trace = _find_traces_for_automation(response["result"], automation_id)[-1]
        assert trace["last_action"] == expected_action
        assert trace["state"] == expected_state
        return trace["run_id"]

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": [
            {"event": "event0"},
            {"event": "event1"},
            {"event": "event2"},
            {"event": "event3"},
            {"event": "event4"},
            {"event": "event5"},
            {"event": "event6"},
            {"event": "event7"},
            {"event": "event8"},
        ],
    }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                sun_config,
            ]
        },
    )

    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client()

    subscription_id = next_id()
    await client.send_json(
        {"id": subscription_id, "type": "automation/debug/breakpoint/subscribe"}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "action/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Trigger "sun" automation
    hass.bus.async_fire("test_event")

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/1", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/1",
        "run_id": run_id,
    }

    # Unsubscribe - execution should resume
    await client.send_json(
        {"id": next_id(), "type": "unsubscribe_events", "subscription": subscription_id}
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await assert_last_action("sun", "action/8", "stopped")

    # Should not be possible to set breakpoints
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "1",
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    # Trigger "sun" automation, should finish without stopping on breakpoints
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    new_run_id = await assert_last_action("sun", "action/8", "stopped")
    assert new_run_id != run_id


async def test_automation_breakpoints_3(hass, hass_ws_client):
    """Test breakpoints can be cleared."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_last_action(automation_id, expected_action, expected_state):
        await client.send_json({"id": next_id(), "type": "automation/trace/list"})
        response = await client.receive_json()
        assert response["success"]
        trace = _find_traces_for_automation(response["result"], automation_id)[-1]
        assert trace["last_action"] == expected_action
        assert trace["state"] == expected_state
        return trace["run_id"]

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": [
            {"event": "event0"},
            {"event": "event1"},
            {"event": "event2"},
            {"event": "event3"},
            {"event": "event4"},
            {"event": "event5"},
            {"event": "event6"},
            {"event": "event7"},
            {"event": "event8"},
        ],
    }

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                sun_config,
            ]
        },
    )

    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_ws_client()

    subscription_id = next_id()
    await client.send_json(
        {"id": subscription_id, "type": "automation/debug/breakpoint/subscribe"}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "action/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/set",
            "automation_id": "sun",
            "node": "action/5",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Trigger "sun" automation
    hass.bus.async_fire("test_event")

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/1", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/1",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/continue",
            "automation_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/5", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/5",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/stop",
            "automation_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await assert_last_action("sun", "action/5", "stopped")

    # Clear 1st breakpoint
    await client.send_json(
        {
            "id": next_id(),
            "type": "automation/debug/breakpoint/clear",
            "automation_id": "sun",
            "node": "action/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Trigger "sun" automation
    hass.bus.async_fire("test_event")

    response = await client.receive_json()
    run_id = await assert_last_action("sun", "action/5", "running")
    assert response["event"] == {
        "automation_id": "sun",
        "node": "action/5",
        "run_id": run_id,
    }
