"""Test Trace websocket API."""
import asyncio
from collections import defaultdict
import json
from typing import Any
from unittest.mock import patch

import pytest
from pytest_unordered import unordered

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.trace.const import DEFAULT_STORED_TRACES
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, CoreState, HomeAssistant, callback
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util.uuid import random_uuid_hex

from tests.common import load_fixture
from tests.typing import WebSocketGenerator


def _find_run_id(traces, trace_type, item_id):
    """Find newest run_id for a script or automation."""
    for trace in reversed(traces):
        if trace["domain"] == trace_type and trace["item_id"] == item_id:
            return trace["run_id"]

    return None


def _find_traces(traces, trace_type, item_id):
    """Find traces for a script or automation."""
    return [
        trace
        for trace in traces
        if trace["domain"] == trace_type and trace["item_id"] == item_id
    ]


async def _setup_automation_or_script(
    hass, domain, configs, script_config=None, stored_traces=None
):
    """Set up automations or scripts from automation config."""
    if domain == "script":
        configs = {config["id"]: {"sequence": config["action"]} for config in configs}

    if script_config:
        if domain == "automation":
            assert await async_setup_component(
                hass, "script", {"script": script_config}
            )
        else:
            configs = {**configs, **script_config}

    if stored_traces is not None:
        if domain == "script":
            for config in configs.values():
                config["trace"] = {}
                config["trace"]["stored_traces"] = stored_traces
        else:
            for config in configs:
                config["trace"] = {}
                config["trace"]["stored_traces"] = stored_traces

    assert await async_setup_component(hass, domain, {domain: configs})


async def _run_automation_or_script(hass, domain, config, event, context=None):
    if domain == "automation":
        hass.bus.async_fire(event, context=context)
    else:
        await hass.services.async_call("script", config["id"], context=context)


def _assert_raw_config(domain, config, trace):
    if domain == "script":
        config = {"sequence": config["action"]}
    assert trace["config"] == config


async def _assert_contexts(client, next_id, contexts, domain=None, item_id=None):
    request = {"id": next_id(), "type": "trace/contexts"}
    if domain is not None:
        request["domain"] = domain
        request["item_id"] = item_id
    await client.send_json(request)
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == contexts


@pytest.mark.parametrize(
    (
        "domain",
        "prefix",
        "extra_trace_keys",
        "trigger",
        "context_key",
        "condition_results",
    ),
    [
        (
            "automation",
            "action",
            [
                {"trigger/0"},
                {"trigger/0", "condition/0"},
                {"trigger/1", "condition/0"},
                {"trigger/0", "condition/0"},
            ],
            [
                "event 'test_event'",
                "event 'test_event2'",
            ],
            "parent_id",
            [True],
        ),
        ("script", "sequence", [set(), set()], [UNDEFINED, UNDEFINED], "id", []),
    ],
)
async def test_get_trace(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client,
    domain,
    prefix,
    extra_trace_keys,
    trigger,
    context_key,
    condition_results,
    enable_custom_integrations: None,
) -> None:
    """Test tracing a script or automation."""
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

    sun_action = {
        "params": {
            "domain": "test",
            "service": "automation",
            "service_data": {},
            "target": {},
        },
        "running_script": False,
    }
    moon_action = {"event": "another_event", "event_data": {}}

    await _setup_automation_or_script(hass, domain, [sun_config, moon_config])

    client = await hass_ws_client()
    contexts = {}
    contexts_sun = {}
    contexts_moon = {}

    # Trigger "sun" automation / run "sun" script
    context = Context()
    await _run_automation_or_script(hass, domain, sun_config, "test_event", context)
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
    assert set(trace["trace"]) == {f"{prefix}/0"} | extra_trace_keys[0]
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    assert trace["trace"][f"{prefix}/0"][0]["error"]
    assert trace["trace"][f"{prefix}/0"][0]["result"] == sun_action
    _assert_raw_config(domain, sun_config, trace)
    assert trace["blueprint_inputs"] is None
    assert trace["context"]
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == "error"
    assert trace["item_id"] == "sun"
    assert trace["context"][context_key] == context.id
    assert trace.get("trigger", UNDEFINED) == trigger[0]
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }
    contexts_sun[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    # Trigger "moon" automation, with passing condition / run "moon" script
    await _run_automation_or_script(hass, domain, moon_config, "test_event2", context)
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
    assert set(trace["trace"]) == {f"{prefix}/0"} | extra_trace_keys[1]
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    assert "error" not in trace["trace"][f"{prefix}/0"][0]
    assert trace["trace"][f"{prefix}/0"][0]["result"] == moon_action
    _assert_raw_config(domain, moon_config, trace)
    assert trace["blueprint_inputs"] is None
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == "finished"
    assert trace["item_id"] == "moon"

    assert trace.get("trigger", UNDEFINED) == trigger[1]

    assert len(trace["trace"].get("condition/0", [])) == len(condition_results)
    for idx, condition_result in enumerate(condition_results):
        assert trace["trace"]["condition/0"][idx]["result"] == {
            "result": condition_result,
            "entities": [],
        }
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }
    contexts_moon[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    if len(extra_trace_keys) <= 2:
        # Check contexts
        await _assert_contexts(client, next_id, contexts)
        await _assert_contexts(client, next_id, contexts_moon, domain, "moon")
        await _assert_contexts(client, next_id, contexts_sun, domain, "sun")
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
    assert set(trace["trace"]) == extra_trace_keys[2]
    assert len(trace["trace"]["condition/0"]) == 1
    assert trace["trace"]["condition/0"][0]["result"] == {
        "result": False,
        "entities": [],
    }
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == "failed_conditions"
    assert trace["trigger"] == "event 'test_event3'"
    assert trace["item_id"] == "moon"
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }
    contexts_moon[trace["context"]["id"]] = {
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
    assert set(trace["trace"]) == {f"{prefix}/0"} | extra_trace_keys[3]
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    assert "error" not in trace["trace"][f"{prefix}/0"][0]
    assert trace["trace"][f"{prefix}/0"][0]["result"] == moon_action
    assert len(trace["trace"]["condition/0"]) == 1
    assert trace["trace"]["condition/0"][0]["result"] == {
        "result": True,
        "entities": [],
    }
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == "finished"
    assert trace["trigger"] == "event 'test_event2'"
    assert trace["item_id"] == "moon"
    contexts[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }
    contexts_moon[trace["context"]["id"]] = {
        "run_id": trace["run_id"],
        "domain": domain,
        "item_id": trace["item_id"],
    }

    # Check contexts
    await _assert_contexts(client, next_id, contexts)
    await _assert_contexts(client, next_id, contexts_moon, domain, "moon")
    await _assert_contexts(client, next_id, contexts_sun, domain, "sun")

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    trace_list = response["result"]

    # Get all traces and generate expected stored traces
    traces = defaultdict(list)
    for trace in trace_list:
        item_id = trace["item_id"]
        run_id = trace["run_id"]
        await client.send_json(
            {
                "id": next_id(),
                "type": "trace/get",
                "domain": domain,
                "item_id": item_id,
                "run_id": run_id,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        traces[f"{domain}.{item_id}"].append(
            {"short_dict": trace, "extended_dict": response["result"]}
        )

    # Fake stop
    assert "trace.saved_traces" not in hass_storage
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Check that saved data is same as the serialized traces
    assert "trace.saved_traces" in hass_storage
    assert hass_storage["trace.saved_traces"]["data"] == traces


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_restore_traces(
    hass: HomeAssistant, hass_storage: dict[str, Any], hass_ws_client, domain
) -> None:
    """Test restored traces."""
    hass.state = CoreState.not_running
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    saved_traces = json.loads(load_fixture(f"trace/{domain}_saved_traces.json"))
    hass_storage["trace.saved_traces"] = saved_traces
    await _setup_automation_or_script(hass, domain, [])
    await hass.async_start()
    await hass.async_block_till_done()

    client = await hass_ws_client()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    trace_list = response["result"]

    # Get all traces and generate expected stored traces
    traces = defaultdict(list)
    contexts = {}
    for trace in trace_list:
        item_id = trace["item_id"]
        run_id = trace["run_id"]
        await client.send_json(
            {
                "id": next_id(),
                "type": "trace/get",
                "domain": domain,
                "item_id": item_id,
                "run_id": run_id,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        traces[f"{domain}.{item_id}"].append(
            {"short_dict": trace, "extended_dict": response["result"]}
        )
        contexts[response["result"]["context"]["id"]] = {
            "run_id": trace["run_id"],
            "domain": domain,
            "item_id": trace["item_id"],
        }

    # Check that loaded data is same as the serialized traces
    assert hass_storage["trace.saved_traces"]["data"] == traces

    # Check restored contexts
    await _assert_contexts(client, next_id, contexts)

    # Fake stop
    hass_storage.pop("trace.saved_traces")
    assert "trace.saved_traces" not in hass_storage
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Check that saved data is same as the serialized traces
    assert "trace.saved_traces" in hass_storage
    assert hass_storage["trace.saved_traces"] == saved_traces


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_get_invalid_trace(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, domain
) -> None:
    """Test getting a non-existing trace."""
    assert await async_setup_component(hass, domain, {domain: {}})
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "trace/get",
            "domain": domain,
            "item_id": "sun",
            "run_id": "invalid",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    ("domain", "stored_traces"),
    [("automation", None), ("automation", 10), ("script", None), ("script", 10)],
)
async def test_trace_overflow(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, domain, stored_traces
) -> None:
    """Test the number of stored traces per script or automation is limited."""
    id = 1

    trace_uuids = []

    def mock_random_uuid_hex():
        nonlocal trace_uuids
        trace_uuids.append(random_uuid_hex())
        return trace_uuids[-1]

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
    await _setup_automation_or_script(
        hass, domain, [sun_config, moon_config], stored_traces=stored_traces
    )

    client = await hass_ws_client()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "sun" and "moon" automation / script once
    await _run_automation_or_script(hass, domain, sun_config, "test_event")
    await _run_automation_or_script(hass, domain, moon_config, "test_event2")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces(response["result"], domain, "moon")) == 1
    assert len(_find_traces(response["result"], domain, "sun")) == 1

    # Trigger "moon" enough times to overflow the max number of stored traces
    with patch(
        "homeassistant.components.trace.models.uuid_util.random_uuid_hex",
        wraps=mock_random_uuid_hex,
    ):
        for _ in range(stored_traces or DEFAULT_STORED_TRACES):
            await _run_automation_or_script(hass, domain, moon_config, "test_event2")
            await hass.async_block_till_done()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    moon_traces = _find_traces(response["result"], domain, "moon")
    assert len(moon_traces) == stored_traces or DEFAULT_STORED_TRACES
    assert moon_traces[0]
    assert moon_traces[0]["run_id"] == trace_uuids[0]
    assert moon_traces[-1]["run_id"] == trace_uuids[-1]
    assert len(_find_traces(response["result"], domain, "sun")) == 1


@pytest.mark.parametrize(
    ("domain", "num_restored_moon_traces"), [("automation", 3), ("script", 1)]
)
async def test_restore_traces_overflow(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client,
    domain,
    num_restored_moon_traces,
) -> None:
    """Test restored traces are evicted first."""
    hass.state = CoreState.not_running
    id = 1

    trace_uuids = []

    def mock_random_uuid_hex():
        nonlocal trace_uuids
        trace_uuids.append(random_uuid_hex())
        return trace_uuids[-1]

    def next_id():
        nonlocal id
        id += 1
        return id

    saved_traces = json.loads(load_fixture(f"trace/{domain}_saved_traces.json"))
    hass_storage["trace.saved_traces"] = saved_traces
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
    await _setup_automation_or_script(hass, domain, [sun_config, moon_config])
    await hass.async_start()
    await hass.async_block_till_done()

    client = await hass_ws_client()

    # Traces should not yet be restored
    assert "trace_traces_restored" not in hass.data

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    restored_moon_traces = _find_traces(response["result"], domain, "moon")
    assert len(restored_moon_traces) == num_restored_moon_traces
    assert len(_find_traces(response["result"], domain, "sun")) == 1

    # Traces should be restored
    assert "trace_traces_restored" in hass.data

    # Trigger "moon" enough times to overflow the max number of stored traces
    with patch(
        "homeassistant.components.trace.models.uuid_util.random_uuid_hex",
        wraps=mock_random_uuid_hex,
    ):
        for _ in range(DEFAULT_STORED_TRACES - num_restored_moon_traces + 1):
            await _run_automation_or_script(hass, domain, moon_config, "test_event2")
            await hass.async_block_till_done()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    moon_traces = _find_traces(response["result"], domain, "moon")
    assert len(moon_traces) == DEFAULT_STORED_TRACES
    if num_restored_moon_traces > 1:
        assert moon_traces[0]["run_id"] == restored_moon_traces[1]["run_id"]
    assert moon_traces[num_restored_moon_traces - 1]["run_id"] == trace_uuids[0]
    assert moon_traces[-1]["run_id"] == trace_uuids[-1]
    assert len(_find_traces(response["result"], domain, "sun")) == 1


@pytest.mark.parametrize(
    ("domain", "num_restored_moon_traces", "restored_run_id"),
    [("automation", 3, "e2c97432afe9b8a42d7983588ed5e6ef"), ("script", 1, "")],
)
async def test_restore_traces_late_overflow(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client,
    domain,
    num_restored_moon_traces,
    restored_run_id,
) -> None:
    """Test restored traces are evicted first."""
    hass.state = CoreState.not_running
    id = 1

    trace_uuids = []

    def mock_random_uuid_hex():
        nonlocal trace_uuids
        trace_uuids.append(random_uuid_hex())
        return trace_uuids[-1]

    def next_id():
        nonlocal id
        id += 1
        return id

    saved_traces = json.loads(load_fixture(f"trace/{domain}_saved_traces.json"))
    hass_storage["trace.saved_traces"] = saved_traces
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
    await _setup_automation_or_script(hass, domain, [sun_config, moon_config])
    await hass.async_start()
    await hass.async_block_till_done()

    client = await hass_ws_client()

    # Traces should not yet be restored
    assert "trace_traces_restored" not in hass.data

    # Trigger "moon" enough times to overflow the max number of stored traces
    with patch(
        "homeassistant.components.trace.models.uuid_util.random_uuid_hex",
        wraps=mock_random_uuid_hex,
    ):
        for _ in range(DEFAULT_STORED_TRACES - num_restored_moon_traces + 1):
            await _run_automation_or_script(hass, domain, moon_config, "test_event2")
            await hass.async_block_till_done()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    moon_traces = _find_traces(response["result"], domain, "moon")
    assert len(moon_traces) == DEFAULT_STORED_TRACES
    if num_restored_moon_traces > 1:
        assert moon_traces[0]["run_id"] == restored_run_id
    assert moon_traces[num_restored_moon_traces - 1]["run_id"] == trace_uuids[0]
    assert moon_traces[-1]["run_id"] == trace_uuids[-1]
    assert len(_find_traces(response["result"], domain, "sun")) == 1


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_trace_no_traces(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, domain
) -> None:
    """Test the storing traces for a script or automation can be disabled."""
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
    await _setup_automation_or_script(hass, domain, [sun_config], stored_traces=0)

    client = await hass_ws_client()

    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    # Trigger "sun" automation / script once
    await _run_automation_or_script(hass, domain, sun_config, "test_event")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces(response["result"], domain, "sun")) == 0


@pytest.mark.parametrize(
    ("domain", "prefix", "trigger", "last_step", "script_execution"),
    [
        (
            "automation",
            "action",
            [
                "event 'test_event'",
                "event 'test_event2'",
                "event 'test_event3'",
                "event 'test_event2'",
            ],
            ["{prefix}/0", "{prefix}/0", "condition/0", "{prefix}/0"],
            ["error", "finished", "failed_conditions", "finished"],
        ),
        (
            "script",
            "sequence",
            [UNDEFINED, UNDEFINED, UNDEFINED, UNDEFINED],
            ["{prefix}/0", "{prefix}/0", "{prefix}/0", "{prefix}/0"],
            ["error", "finished", "finished", "finished"],
        ),
    ],
)
async def test_list_traces(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    domain,
    prefix,
    trigger,
    last_step,
    script_execution,
) -> None:
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
    await _setup_automation_or_script(hass, domain, [sun_config, moon_config])

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
    await _run_automation_or_script(hass, domain, sun_config, "test_event")
    await hass.async_block_till_done()

    # List traces
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
    await _run_automation_or_script(hass, domain, moon_config, "test_event2")
    await hass.async_block_till_done()

    # Trigger "moon" automation, with failing condition / run "moon" script
    await _run_automation_or_script(hass, domain, moon_config, "test_event3")
    await hass.async_block_till_done()

    # Trigger "moon" automation, with passing condition / run "moon" script
    await _run_automation_or_script(hass, domain, moon_config, "test_event2")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces(response["result"], domain, "moon")) == 3
    assert len(_find_traces(response["result"], domain, "sun")) == 1
    trace = _find_traces(response["result"], domain, "sun")[0]
    assert trace["last_step"] == last_step[0].format(prefix=prefix)
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == script_execution[0]
    assert trace["timestamp"]
    assert trace["item_id"] == "sun"
    assert trace.get("trigger", UNDEFINED) == trigger[0]

    trace = _find_traces(response["result"], domain, "moon")[0]
    assert trace["last_step"] == last_step[1].format(prefix=prefix)
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == script_execution[1]
    assert trace["timestamp"]
    assert trace["item_id"] == "moon"
    assert trace.get("trigger", UNDEFINED) == trigger[1]

    trace = _find_traces(response["result"], domain, "moon")[1]
    assert trace["last_step"] == last_step[2].format(prefix=prefix)
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == script_execution[2]
    assert trace["timestamp"]
    assert trace["item_id"] == "moon"
    assert trace.get("trigger", UNDEFINED) == trigger[2]

    trace = _find_traces(response["result"], domain, "moon")[2]
    assert trace["last_step"] == last_step[3].format(prefix=prefix)
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == script_execution[3]
    assert trace["timestamp"]
    assert trace["item_id"] == "moon"
    assert trace.get("trigger", UNDEFINED) == trigger[3]


@pytest.mark.parametrize(
    ("domain", "prefix", "extra_trace_keys"),
    [("automation", "action", {"trigger/0"}), ("script", "sequence", set())],
)
async def test_nested_traces(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    domain,
    prefix,
    extra_trace_keys,
) -> None:
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
    moon_config = {"moon": {"sequence": {"event": "another_event"}}}
    await _setup_automation_or_script(hass, domain, [sun_config], moon_config)

    client = await hass_ws_client()

    # Trigger "sun" automation / run "sun" script
    await _run_automation_or_script(hass, domain, sun_config, "test_event")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    assert len(_find_traces(response["result"], "script", "moon")) == 1
    moon_run_id = _find_run_id(response["result"], "script", "moon")
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": domain})
    response = await client.receive_json()
    assert response["success"]
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
    assert set(trace["trace"]) == {f"{prefix}/0"} | extra_trace_keys
    assert len(trace["trace"][f"{prefix}/0"]) == 1
    child_id = trace["trace"][f"{prefix}/0"][0]["child_id"]
    assert child_id == {"domain": "script", "item_id": "moon", "run_id": moon_run_id}


@pytest.mark.parametrize(
    ("domain", "prefix"), [("automation", "action"), ("script", "sequence")]
)
async def test_breakpoints(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, domain, prefix
) -> None:
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
    await _setup_automation_or_script(hass, domain, [sun_config])

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
    assert response["result"] == unordered(
        [
            {"node": f"{prefix}/1", "run_id": "*", "domain": domain, "item_id": "sun"},
            {"node": f"{prefix}/5", "run_id": "*", "domain": domain, "item_id": "sun"},
        ],
    )

    # Trigger "sun" automation / run "sun" script
    await _run_automation_or_script(hass, domain, sun_config, "test_event")

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
    ("domain", "prefix"), [("automation", "action"), ("script", "sequence")]
)
async def test_breakpoints_2(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, domain, prefix
) -> None:
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
    await _setup_automation_or_script(hass, domain, [sun_config])

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
    await _run_automation_or_script(hass, domain, sun_config, "test_event")

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
    await _run_automation_or_script(hass, domain, sun_config, "test_event")
    await hass.async_block_till_done()

    new_run_id = await assert_last_step("sun", f"{prefix}/8", "stopped")
    assert new_run_id != run_id


@pytest.mark.parametrize(
    ("domain", "prefix"), [("automation", "action"), ("script", "sequence")]
)
async def test_breakpoints_3(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, domain, prefix
) -> None:
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
    await _setup_automation_or_script(hass, domain, [sun_config])

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
    await _run_automation_or_script(hass, domain, sun_config, "test_event")

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
    await _run_automation_or_script(hass, domain, sun_config, "test_event")

    response = await client.receive_json()
    run_id = await assert_last_step("sun", f"{prefix}/5", "running")
    assert response["event"] == {
        "domain": domain,
        "item_id": "sun",
        "node": f"{prefix}/5",
        "run_id": run_id,
    }


@pytest.mark.parametrize(
    ("script_mode", "max_runs", "script_execution"),
    [
        ({"mode": "single"}, 1, "failed_single"),
        ({"mode": "parallel", "max": 2}, 2, "failed_max_runs"),
    ],
)
async def test_script_mode(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    script_mode,
    max_runs,
    script_execution,
) -> None:
    """Test overlapping runs with max_runs > 1."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    flag = asyncio.Event()

    @callback
    def _handle_event(_):
        flag.set()

    event = "test_event"
    script_config = {
        "script1": {
            "sequence": [
                {"event": event, "event_data": {"value": 1}},
                {"wait_template": "{{ states.switch.test.state == 'off' }}"},
                {"event": event, "event_data": {"value": 2}},
            ],
            **script_mode,
        },
    }
    client = await hass_ws_client()
    hass.bus.async_listen(event, _handle_event)
    assert await async_setup_component(hass, "script", {"script": script_config})

    for _ in range(max_runs):
        hass.states.async_set("switch.test", "on")
        await hass.services.async_call("script", "script1")
        await asyncio.wait_for(flag.wait(), 1)

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    traces = _find_traces(response["result"], "script", "script1")
    assert len(traces) == max_runs
    for trace in traces:
        assert trace["state"] == "running"

    # Start additional run of script while first runs are suspended in wait_template.

    flag.clear()
    await hass.services.async_call("script", "script1")

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    traces = _find_traces(response["result"], "script", "script1")
    assert len(traces) == max_runs + 1
    assert traces[-1]["state"] == "stopped"
    assert traces[-1]["script_execution"] == script_execution


@pytest.mark.parametrize(
    ("script_mode", "script_execution"),
    [("restart", "cancelled"), ("parallel", "finished")],
)
async def test_script_mode_2(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    script_mode,
    script_execution,
) -> None:
    """Test overlapping runs with max_runs > 1."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    flag = asyncio.Event()

    @callback
    def _handle_event(_):
        flag.set()

    event = "test_event"
    script_config = {
        "script1": {
            "sequence": [
                {"event": event, "event_data": {"value": 1}},
                {"wait_template": "{{ states.switch.test.state == 'off' }}"},
                {"event": event, "event_data": {"value": 2}},
            ],
            "mode": script_mode,
        }
    }
    client = await hass_ws_client()
    hass.bus.async_listen(event, _handle_event)
    assert await async_setup_component(hass, "script", {"script": script_config})

    hass.states.async_set("switch.test", "on")
    await hass.services.async_call("script", "script1")
    await asyncio.wait_for(flag.wait(), 1)

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    trace = _find_traces(response["result"], "script", "script1")[0]
    assert trace["state"] == "running"

    # Start second run of script while first run is suspended in wait_template.

    flag.clear()
    await hass.services.async_call("script", "script1")
    await asyncio.wait_for(flag.wait(), 1)

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    trace = _find_traces(response["result"], "script", "script1")[1]
    assert trace["state"] == "running"

    # Let both scripts finish
    hass.states.async_set("switch.test", "off")
    await hass.async_block_till_done()

    # List traces
    await client.send_json({"id": next_id(), "type": "trace/list", "domain": "script"})
    response = await client.receive_json()
    assert response["success"]
    trace = _find_traces(response["result"], "script", "script1")[0]
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == script_execution
    trace = _find_traces(response["result"], "script", "script1")[1]
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == "finished"


async def test_trace_blueprint_automation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    enable_custom_integrations: None,
) -> None:
    """Test trace of blueprint automation."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    domain = "automation"
    sun_config = {
        "id": "sun",
        "use_blueprint": {
            "path": "test_event_service.yaml",
            "input": {
                "trigger_event": "blueprint_event",
                "service_to_call": "test.automation",
                "a_number": 5,
            },
        },
    }
    sun_action = {
        "params": {
            "domain": "test",
            "service": "automation",
            "service_data": {},
            "target": {"entity_id": ["light.kitchen"]},
        },
        "running_script": False,
    }
    assert await async_setup_component(hass, "automation", {"automation": sun_config})
    client = await hass_ws_client()
    hass.bus.async_fire("blueprint_event")
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
    assert set(trace["trace"]) == {"trigger/0", "action/0"}
    assert len(trace["trace"]["action/0"]) == 1
    assert trace["trace"]["action/0"][0]["error"]
    assert trace["trace"]["action/0"][0]["result"] == sun_action
    assert trace["config"]["id"] == "sun"
    assert trace["blueprint_inputs"] == sun_config
    assert trace["context"]
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["script_execution"] == "error"
    assert trace["item_id"] == "sun"
    assert trace.get("trigger", UNDEFINED) == "event 'blueprint_event'"
