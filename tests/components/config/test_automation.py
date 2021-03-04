"""Test Automation config panel."""
import json
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config

from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


async def test_get_device_config(hass, hass_client):
    """Test getting device config."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    def mock_read(path):
        """Mock reading data."""
        return [{"id": "sun"}, {"id": "moon"}]

    with patch("homeassistant.components.config._read", mock_read):
        resp = await client.get("/api/config/automation/config/moon")

    assert resp.status == 200
    result = await resp.json()

    assert result == {"id": "moon"}


async def test_update_device_config(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.post(
            "/api/config/automation/config/moon",
            data=json.dumps({"trigger": [], "action": [], "condition": []}),
        )

    assert resp.status == 200
    result = await resp.json()
    assert result == {"result": "ok"}

    assert list(orig_data[1]) == ["id", "trigger", "condition", "action"]
    assert orig_data[1] == {"id": "moon", "trigger": [], "condition": [], "action": []}
    assert written[0] == orig_data


async def test_bad_formatted_automations(hass, hass_client):
    """Test that we handle automations without ID."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = [
        {
            # No ID
            "action": {"event": "hello"}
        },
        {"id": "moon"},
    ]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.post(
            "/api/config/automation/config/moon",
            data=json.dumps({"trigger": [], "action": [], "condition": []}),
        )
        await hass.async_block_till_done()

    assert resp.status == 200
    result = await resp.json()
    assert result == {"result": "ok"}

    # Verify ID added to orig_data
    assert "id" in orig_data[0]

    assert orig_data[1] == {"id": "moon", "trigger": [], "condition": [], "action": []}


async def test_delete_automation(hass, hass_client):
    """Test deleting an automation."""
    ent_reg = await hass.helpers.entity_registry.async_get_registry()

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "sun",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {"service": "test.automation"},
                },
                {
                    "id": "moon",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": {"service": "test.automation"},
                },
            ]
        },
    )

    assert len(ent_reg.entities) == 2

    with patch.object(config, "SECTIONS", ["automation"]):
        assert await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        resp = await client.delete("/api/config/automation/config/sun")
        await hass.async_block_till_done()

    assert resp.status == 200
    result = await resp.json()
    assert result == {"result": "ok"}

    assert len(written) == 1
    assert written[0][0]["id"] == "moon"

    assert len(ent_reg.entities) == 1


async def test_get_automation_trace(hass, hass_ws_client):
    """Test deleting an automation."""
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

    await client.send_json({"id": next_id(), "type": "automation/trace"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {"id": next_id(), "type": "automation/trace", "automation_id": "sun"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"sun": []}

    # Trigger "sun" automation
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json({"id": next_id(), "type": "automation/trace"})
    response = await client.receive_json()
    assert response["success"]
    assert "moon" not in response["result"]
    assert len(response["result"]["sun"]) == 1
    trace = response["result"]["sun"][0]
    assert len(trace["action_trace"]) == 1
    assert len(trace["action_trace"]["action/0"]) == 1
    assert trace["action_trace"]["action/0"][0]["error"]
    assert "result" not in trace["action_trace"]["action/0"][0]
    assert trace["condition_trace"] == {}
    assert trace["config"] == sun_config
    assert trace["context"]
    assert trace["error"] == "Unable to find service test.automation"
    assert trace["state"] == "stopped"
    assert trace["trigger"]["description"] == "event 'test_event'"
    assert trace["unique_id"] == "sun"
    assert trace["variables"]

    # Trigger "moon" automation, with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json(
        {"id": next_id(), "type": "automation/trace", "automation_id": "moon"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert "sun" not in response["result"]
    assert len(response["result"]["moon"]) == 1
    trace = response["result"]["moon"][0]
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
    assert trace["trigger"]["description"] == "event 'test_event2'"
    assert trace["unique_id"] == "moon"
    assert trace["variables"]

    # Trigger "moon" automation, with failing condition
    hass.bus.async_fire("test_event3")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json(
        {"id": next_id(), "type": "automation/trace", "automation_id": "moon"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert "sun" not in response["result"]
    assert len(response["result"]["moon"]) == 2
    trace = response["result"]["moon"][1]
    assert len(trace["action_trace"]) == 0
    assert len(trace["condition_trace"]) == 1
    assert len(trace["condition_trace"]["condition/0"]) == 1
    assert trace["condition_trace"]["condition/0"][0]["result"] == {"result": False}
    assert trace["config"] == moon_config
    assert trace["context"]
    assert "error" not in trace
    assert trace["state"] == "stopped"
    assert trace["trigger"]["description"] == "event 'test_event3'"
    assert trace["unique_id"] == "moon"
    assert trace["variables"]

    # Trigger "moon" automation, with passing condition
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()

    # Get trace
    await client.send_json(
        {"id": next_id(), "type": "automation/trace", "automation_id": "moon"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert "sun" not in response["result"]
    assert len(response["result"]["moon"]) == 3
    trace = response["result"]["moon"][2]
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
    assert trace["trigger"]["description"] == "event 'test_event2'"
    assert trace["unique_id"] == "moon"
    assert trace["variables"]
