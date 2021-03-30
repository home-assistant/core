"""Test Trace websocket API."""
import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.trace.const import STORED_TRACES
from homeassistant.core import Context

from tests.common import assert_lists_same


def _find_run_id(traces, trace_type, item_id):
    """Find newest run_id for an script or automation."""
    for trace in reversed(traces):
        if trace["domain"] == trace_type and trace["item_id"] == item_id:
            return trace["run_id"]

    return None


def _find_traces(traces, trace_type, item_id):
    """Find traces for an script or automation."""
    return [
        trace
        for trace in traces
        if trace["domain"] == trace_type and trace["item_id"] == item_id
    ]


@pytest.mark.parametrize(
    "domain, prefix", [("automation", "action"), ("script", "sequence")]
)
async def test_get_trace(hass, hass_ws_client, domain, prefix):
    """Test tracing an script or automation."""
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
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}
        moon_config = {"sequence": moon_config["action"]}

    sun_action = {
        "limit": 10,
        "params": {
            "domain": "test",
            "service": "automation",
            "service_data": {},
            "target": {},
        },
        "running_script": False,
    }
    moon_action = {"event": "another_event", "event_data": {}}

    if domain == "automation":
        assert await async_setup_component(
            hass, domain, {domain: [sun_config, moon_config]}
        )
    else:
        assert await async_setup_component(
            hass, domain, {domain: {"sun": sun_config, "moon": moon_config}}
        )

    client = await hass_ws_client()
    contexts = {}

    # Trigger "sun" automation / run "sun" script
    context = Context()
    if domain == "automation":
        hass.bus.async_fire("test_event", context=context)
    else:
        await hass.services.async_call("script", "sun", context=context)
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], domain, "sun")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": domain,
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    if domain == "automation":
        assert len(trace["trace"]) == 2
        assert set(trace["trace"]) == {"trigger", f"{prefix}/0"}
    else:
        assert len(trace["trace"]) == 1
        assert set(trace["trace"]) == {f"{prefix}/0"}
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    assert trace["trace"][f"{prefix}/0"][0]["error"]
    assert trace["trace"][f"{prefix}/0"][0]["result"] == sun_action
    assert trace["config"] == sun_config
    assert trace["context"]
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["item_id"] == "sun"
    if domain == "automation":
        assert trace["context"]["parent_id"] == context.id
        assert trace["trigger"] == "event 'test_event'"
    else:
        assert trace["context"]["id"] == context.id
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    # Trigger "moon" automation, with passing condition / run "moon" script
    if domain == "automation":
        hass.bus.async_fire("test_event2")
    else:
        await hass.services.async_call("script", "moon")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], domain, "moon")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": domain,
            "item_id": "moon",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    if domain == "automation":
        assert len(trace["trace"]) == 3
        assert set(trace["trace"]) == {"trigger", "condition/0", f"{prefix}/0"}
    else:
        assert len(trace["trace"]) == 1
        assert set(trace["trace"]) == {f"{prefix}/0"}
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    assert "error" not in trace["trace"][f"{prefix}/0"][0]
    assert trace["trace"][f"{prefix}/0"][0]["result"] == moon_action
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["item_id"] == "moon"

    if domain == "automation":
        assert len(trace["trace"]["condition/0"]) == 1
        assert trace["trace"]["condition/0"][0]["result"] == {"result": True}
        assert trace["trigger"] == "event 'test_event2'"
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    if domain == "script":
        # Check contexts
        await client.send_json({"id": next_id(), "type": "trace/contexts"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == contexts
        return

    # Trigger "moon" automation with failing condition
    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "automation", "moon")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": domain,
            "item_id": "moon",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    if domain == "automation":
        assert len(trace["trace"]) == 2
        assert set(trace["trace"]) == {"trigger", "condition/0"}
    else:
        assert len(trace["trace"]) == 1
        assert set(trace["trace"]) == {f"{prefix}/0"}
    assert len(trace["trace"]["condition/0"]) == 1
    assert trace["trace"]["condition/0"][0]["result"] == {"result": False}
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["trigger"] == "event 'test_event3'"
    assert trace["item_id"] == "moon"
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    # Trigger "moon" automation with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    run_id = _find_run_id(response["result"], "automation", "moon")

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": domain,
            "item_id": "moon",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    assert len(trace["trace"]) == 3
    assert set(trace["trace"]) == {"trigger", "condition/0", f"{prefix}/0"}
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    assert "error" not in trace["trace"][f"{prefix}/0"][0]
    assert trace["trace"][f"{prefix}/0"][0]["result"] == moon_action
    assert len(trace["trace"]["condition/0"]) == 1
    assert trace["trace"]["condition/0"][0]["result"] == {"result": True}
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["trigger"] == "event 'test_event2'"
    assert trace["item_id"] == "moon"
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    # Check contexts
    await client.send_json({"id": next_id(), "type": "trace/contexts"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == contexts


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_trace_overflow(hass, hass_ws_client, domain):
    """Test the number of stored traces per script or automation is limited."""
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
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}
        moon_config = {"sequence": moon_config["action"]}

    if domain == "automation":
        assert await async_setup_component(
            hass, domain, {domain: [sun_config, moon_config]}
        )
    else:
        assert await async_setup_component(
            hass, domain, {domain: {"sun": sun_config, "moon": moon_config}}
        )

    client = await hass_ws_client()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "sun" and "moon" automation / script once
    if domain == "automation":
        hass.bus.async_fire("test_event")
        hass.bus.async_fire("test_event2")
    else:
        await hass.services.async_call("script", "sun")
        await hass.services.async_call("script", "moon")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces(response["result"], domain, "moon")) == 1
    moon_run_id = _find_run_id(response["result"], domain, "moon")
    assert len(_find_traces(response["result"], domain, "sun")) == 1

    # Trigger "moon" enough times to overflow the max number of stored traces
    for _ in range(STORED_TRACES):
        if domain == "automation":
            hass.bus.async_fire("test_event2")
        else:
            await hass.services.async_call("script", "moon")
        await hass.async_block_till_done()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    moon_traces = _find_traces(response["result"], domain, "moon")
    assert len(moon_traces) == STORED_TRACES
    assert moon_traces[0]
    assert int(moon_traces[0]["run_id"]) == int(moon_run_id) + 1
    assert int(moon_traces[-1]["run_id"]) == int(moon_run_id) + STORED_TRACES
    assert len(_find_traces(response["result"], domain, "sun")) == 1


@pytest.mark.parametrize(
    "domain, prefix", [("automation", "action"), ("script", "sequence")]
)
async def test_list_traces(hass, hass_ws_client, domain, prefix):
    """Test listing script and automation traces."""
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
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}
        moon_config = {"sequence": moon_config["action"]}

    if domain == "automation":
        assert await async_setup_component(
            hass, domain, {domain: [sun_config, moon_config]}
        )
    else:
        assert await async_setup_component(
            hass, domain, {domain: {"sun": sun_config, "moon": moon_config}}
        )

    client = await hass_ws_client()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    await client.send_json(
        {"id": next_id(), "type": "trace/list", "domain": domain, "item_id": "sun"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "sun" automation / run "sun" script
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert len(_find_traces(response["result"], domain, "sun")) == 1

    await client.send_json(
        {"id": next_id(), "type": "trace/list", "domain": domain, "item_id": "sun"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert len(_find_traces(response["result"], domain, "sun")) == 1

    await client.send_json(
        {"id": next_id(), "type": "trace/list", "domain": domain, "item_id": "moon"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "moon" automation, with passing condition / run "moon" script
    if domain == "automation":
        hass.bus.async_fire("test_event2")
    else:
        await hass.services.async_call("script", "moon")
    await hass.async_block_till_done()

    # Trigger "moon" automation, with failing condition / run "moon" script
    if domain == "automation":
        hass.bus.async_fire("test_event3")
    else:
        await hass.services.async_call("script", "moon")
    await hass.async_block_till_done()

    # Trigger "moon" automation, with passing condition / run "moon" script
    if domain == "automation":
        hass.bus.async_fire("test_event2")
    else:
        await hass.services.async_call("script", "moon")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces(response["result"], domain, "moon")) == 3
    assert len(_find_traces(response["result"], domain, "sun")) == 1
    trace = _find_traces(response["result"], domain, "sun")[0]
    assert trace["last_step"] == f"{prefix}/0"
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["item_id"] == "sun"
    if domain == "automation":
        assert trace["trigger"] == "event 'test_event'"

    trace = _find_traces(response["result"], domain, "moon")[0]
    assert trace["last_step"] == f"{prefix}/0"
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["item_id"] == "moon"
    if domain == "automation":
        assert trace["trigger"] == "event 'test_event2'"

    trace = _find_traces(response["result"], domain, "moon")[1]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["item_id"] == "moon"
    if domain == "automation":
        assert trace["last_step"] == "condition/0"
        assert trace["trigger"] == "event 'test_event3'"
    else:
        assert trace["last_step"] == f"{prefix}/0"

    trace = _find_traces(response["result"], domain, "moon")[2]
    assert trace["last_step"] == f"{prefix}/0"
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["timestamp"]
    assert trace["item_id"] == "moon"
    if domain == "automation":
        assert trace["trigger"] == "event 'test_event2'"


@pytest.mark.parametrize(
    "domain, prefix", [("automation", "action"), ("script", "sequence")]
)
async def test_nested_traces(hass, hass_ws_client, domain, prefix):
    """Test nested automation and script traces."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    sun_config = {
        "id": "sun",
        "trigger": {"platform": "event", "event_type": "test_event"},
        "action": {"service": "script.moon"},
    }
    moon_config = {
        "sequence": {"event": "another_event"},
    }
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}

    if domain == "automation":
        assert await async_setup_component(hass, domain, {domain: [sun_config]})
        assert await async_setup_component(
            hass, "script", {"script": {"moon": moon_config}}
        )
    else:
        assert await async_setup_component(
            hass, domain, {domain: {"sun": sun_config, "moon": moon_config}}
        )

    client = await hass_ws_client()

    # Trigger "sun" automation / run "sun" script
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    if domain == "automation":
        assert len(response["result"]) == 1
    else:
        assert len(response["result"]) == 2
    assert len(_find_traces(response["result"], "script", "moon")) == 1
    moon_run_id = _find_run_id(response["result"], "script", "moon")
    if domain == "automation":
        await client.send_json(
            {"id": next_id(), "type": "trace/list", "domain": "automation"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert len(response["result"]) == 1
    assert len(_find_traces(response["result"], domain, "sun")) == 1
    sun_run_id = _find_run_id(response["result"], domain, "sun")
    assert sun_run_id != moon_run_id

    # Get trace
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/get",
            "domain": domain,
            "item_id": "sun",
            "run_id": sun_run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    trace = response["result"]
    if domain == "automation":
        assert len(trace["trace"]) == 2
        assert set(trace["trace"]) == {"trigger", f"{prefix}/0"}
    else:
        assert len(trace["trace"]) == 1
        assert set(trace["trace"]) == {f"{prefix}/0"}
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    child_id = trace["trace"][f"{prefix}/0"][0]["child_id"]
    assert child_id == {"domain": "script", "item_id": "moon", "run_id": moon_run_id}


@pytest.mark.parametrize(
    "domain, prefix", [("automation", "action"), ("script", "sequence")]
)
async def test_breakpoints(hass, hass_ws_client, domain, prefix):
    """Test script and automation breakpoints."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_last_step(item_id, expected_action, expected_state):
        await client.send_json(
            {"id": next_id(), "type": "trace/list", "domain": domain}
        )
        response = await client.receive_json()
        assert response["success"]
        trace = _find_traces(response["result"], domain, item_id)[-1]
        assert trace["last_step"] == expected_action
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
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}

    if domain == "automation":
        assert await async_setup_component(hass, domain, {domain: [sun_config]})
    else:
        assert await async_setup_component(hass, domain, {domain: {"sun": sun_config}})

    client = await hass_ws_client()

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": "1",
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json({"id": next_id(), "type": "trace/debug/breakpoint/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    subscription_id = next_id()
    await client.send_json(
        {"id": subscription_id, "type": "trace/debug/breakpoint/subscribe"}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": f"{prefix}/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": f"{prefix}/5",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json({"id": next_id(), "type": "trace/debug/breakpoint/list"})
    response = await client.receive_json()
    assert response["success"]
    assert_lists_same(
        response["result"],
        [
            {"node": f"{prefix}/1", "run_id": "*", "domain": domain, "item_id": "sun"},
            {"node": f"{prefix}/5", "run_id": "*", "domain": domain, "item_id": "sun"},
        ],
    )

    # Trigger "sun" automation / run "sun" script
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/1", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/1",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/step",
            "domain": domain,
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/2", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/2",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/continue",
            "domain": domain,
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/5", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/5",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/stop",
            "domain": domain,
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await assert_last_step("sun", f"{prefix}/5", "stopped")


@pytest.mark.parametrize(
    "domain, prefix", [("automation", "action"), ("script", "sequence")]
)
async def test_breakpoints_2(hass, hass_ws_client, domain, prefix):
    """Test execution resumes and breakpoints are removed after subscription removed."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_last_step(item_id, expected_action, expected_state):
        await client.send_json(
            {"id": next_id(), "type": "trace/list", "domain": domain}
        )
        response = await client.receive_json()
        assert response["success"]
        trace = _find_traces(response["result"], domain, item_id)[-1]
        assert trace["last_step"] == expected_action
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
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}

    if domain == "automation":
        assert await async_setup_component(hass, domain, {domain: [sun_config]})
    else:
        assert await async_setup_component(hass, domain, {domain: {"sun": sun_config}})

    client = await hass_ws_client()

    subscription_id = next_id()
    await client.send_json(
        {"id": subscription_id, "type": "trace/debug/breakpoint/subscribe"}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": f"{prefix}/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Trigger "sun" automation / run "sun" script
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/1", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/1",
        "run_id": run_id,
    }

    # Unsubscribe - execution should resume
    await client.send_json(
        {"id": next_id(), "type": "unsubscribe_events", "subscription": subscription_id}
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await assert_last_step("sun", f"{prefix}/8", "stopped")

    # Should not be possible to set breakpoints
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": "1",
        }
    )
    response = await client.receive_json()
    assert not response["success"]

    # Trigger "sun" automation / script, should finish without stopping on breakpoints
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")
    await hass.async_block_till_done()

    new_run_id = await assert_last_step("sun", f"{prefix}/8", "stopped")
    assert new_run_id != run_id


@pytest.mark.parametrize(
    "domain, prefix", [("automation", "action"), ("script", "sequence")]
)
async def test_breakpoints_3(hass, hass_ws_client, domain, prefix):
    """Test breakpoints can be cleared."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_last_step(item_id, expected_action, expected_state):
        await client.send_json(
            {"id": next_id(), "type": "trace/list", "domain": domain}
        )
        response = await client.receive_json()
        assert response["success"]
        trace = _find_traces(response["result"], domain, item_id)[-1]
        assert trace["last_step"] == expected_action
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
    if domain == "script":
        sun_config = {"sequence": sun_config["action"]}

    if domain == "automation":
        assert await async_setup_component(hass, domain, {domain: [sun_config]})
    else:
        assert await async_setup_component(hass, domain, {domain: {"sun": sun_config}})

    client = await hass_ws_client()

    subscription_id = next_id()
    await client.send_json(
        {"id": subscription_id, "type": "trace/debug/breakpoint/subscribe"}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": f"{prefix}/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/set",
            "domain": domain,
            "item_id": "sun",
            "node": f"{prefix}/5",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Trigger "sun" automation / run "sun" script
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/1", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/1",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/continue",
            "domain": domain,
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/5", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/5",
        "run_id": run_id,
    }

    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/stop",
            "domain": domain,
            "item_id": "sun",
            "run_id": run_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await assert_last_step("sun", f"{prefix}/5", "stopped")

    # Clear 1st breakpoint
    await client.send_json(
        {
            "id": next_id(),
            "type": "trace/debug/breakpoint/clear",
            "domain": domain,
            "item_id": "sun",
            "node": f"{prefix}/1",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    # Trigger "sun" automation / run "sun" script
    if domain == "automation":
        hass.bus.async_fire("test_event")
    else:
        await hass.services.async_call("script", "sun")

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/5", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/5",
        "run_id": run_id,
    }
