"""The tests for the webhook automation trigger."""
from unittest.mock import patch

import pytest

from homeassistant.core import callback
from homeassistant.setup import async_setup_component

from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture(autouse=True)
async def setup_http(hass):
    """Set up http."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "webhook", {})
    await hass.async_block_till_done()


async def test_webhook_json(hass, hass_client_no_auth):
    """Test triggering with a JSON webhook."""
    events = []

    @callback
    def store_event(event):
        """Help store events."""
        events.append(event)

    hass.bus.async_listen("test_success", store_event)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "webhook", "webhook_id": "json_webhook"},
                "action": {
                    "event": "test_success",
                    "event_data_template": {
                        "hello": "yo {{ trigger.json.hello }}",
                        "id": "{{ trigger.id}}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/json_webhook", json={"hello": "world"})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"
    assert events[0].data["id"] == 0


async def test_webhook_post(hass, hass_client_no_auth):
    """Test triggering with a POST webhook."""
    events = []

    @callback
    def store_event(event):
        """Help store events."""
        events.append(event)

    hass.bus.async_listen("test_success", store_event)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "webhook", "webhook_id": "post_webhook"},
                "action": {
                    "event": "test_success",
                    "event_data_template": {"hello": "yo {{ trigger.data.hello }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/post_webhook", data={"hello": "world"})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"


async def test_webhook_query(hass, hass_client_no_auth):
    """Test triggering with a query POST webhook."""
    events = []

    @callback
    def store_event(event):
        """Help store events."""
        events.append(event)

    hass.bus.async_listen("test_success", store_event)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "webhook", "webhook_id": "query_webhook"},
                "action": {
                    "event": "test_success",
                    "event_data_template": {"hello": "yo {{ trigger.query.hello }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/query_webhook?hello=world")
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"


async def test_webhook_multiple(hass, hass_client_no_auth):
    """Test triggering multiple triggers with a POST webhook."""
    events1 = []
    events2 = []

    @callback
    def store_event1(event):
        """Help store events."""
        events1.append(event)

    @callback
    def store_event2(event):
        """Help store events."""
        events2.append(event)

    hass.bus.async_listen("test_success1", store_event1)
    hass.bus.async_listen("test_success2", store_event2)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "trigger": {"platform": "webhook", "webhook_id": "post_webhook"},
                    "action": {
                        "event": "test_success1",
                        "event_data_template": {"hello": "yo {{ trigger.data.hello }}"},
                    },
                },
                {
                    "trigger": {"platform": "webhook", "webhook_id": "post_webhook"},
                    "action": {
                        "event": "test_success2",
                        "event_data_template": {
                            "hello": "yo2 {{ trigger.data.hello }}"
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/post_webhook", data={"hello": "world"})
    await hass.async_block_till_done()

    assert len(events1) == 1
    assert events1[0].data["hello"] == "yo world"
    assert len(events2) == 1
    assert events2[0].data["hello"] == "yo2 world"


async def test_webhook_reload(hass, hass_client_no_auth):
    """Test reloading a webhook."""
    events = []

    @callback
    def store_event(event):
        """Help store events."""
        events.append(event)

    hass.bus.async_listen("test_success", store_event)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "webhook", "webhook_id": "post_webhook"},
                "action": {
                    "event": "test_success",
                    "event_data_template": {"hello": "yo {{ trigger.data.hello }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/post_webhook", data={"hello": "world"})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            "automation": {
                "trigger": {"platform": "webhook", "webhook_id": "post_webhook"},
                "action": {
                    "event": "test_success",
                    "event_data_template": {"hello": "yo2 {{ trigger.data.hello }}"},
                },
            }
        },
    ):
        await hass.services.async_call(
            "automation",
            "reload",
            blocking=True,
        )
        await hass.async_block_till_done()

    await client.post("/api/webhook/post_webhook", data={"hello": "world"})
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[1].data["hello"] == "yo2 world"
