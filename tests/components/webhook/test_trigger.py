"""The tests for the webhook automation trigger."""

import asyncio
import hashlib
from ipaddress import ip_address
from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import async_capture_events
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.webhook import DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_http(hass: HomeAssistant) -> None:
    """Set up http."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_webhook_json(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
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


async def test_webhook_post(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test triggering with a POST webhook."""
    # Set up fake cloud
    hass.config.components.add("cloud")

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
                "trigger": {
                    "platform": "webhook",
                    "webhook_id": "post_webhook",
                    "local_only": True,
                },
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

    # Request from remote IP
    with patch(
        "homeassistant.components.webhook.ip_address",
        return_value=ip_address("123.123.123.123"),
    ):
        await client.post("/api/webhook/post_webhook", data={"hello": "world"})
    # No hook received
    await hass.async_block_till_done()
    assert len(events) == 1

    # Request from Home Assistant Cloud remote UI
    with patch(
        "hass_nabucasa.remote.is_cloud_request", Mock(get=Mock(return_value=True))
    ):
        await client.post("/api/webhook/post_webhook", data={"hello": "world"})

    # No hook received
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_webhook_allowed_methods_internet(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test the webhook obeys allowed_methods and local_only options."""
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
                "trigger": {
                    "platform": "webhook",
                    "webhook_id": "post_webhook",
                    "allowed_methods": "PUT",
                    "local_only": False,
                },
                "action": {
                    "event": "test_success",
                },
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/post_webhook")
    await hass.async_block_till_done()

    assert len(events) == 0

    # Request from remote IP
    with patch(
        "homeassistant.components.webhook.ip_address",
        return_value=ip_address("123.123.123.123"),
    ):
        await client.put("/api/webhook/post_webhook")
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_webhook_query(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
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


async def test_webhook_multiple(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
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


async def test_webhook_reload(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
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


async def test_webhook_template(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test triggering with a template webhook."""
    # Set up fake cloud
    hass.config.components.add("cloud")

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
                "trigger": {
                    "platform": "webhook",
                    "webhook_id": "webhook-{{ sqrt(9)|round }}",
                    "local_only": True,
                },
                "action": {
                    "event": "test_success",
                    "event_data_template": {"hello": "yo {{ trigger.data.hello }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/webhook-3", data={"hello": "world"})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"


async def test_webhook_template_uses_state(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test a template webhook ID is rendered with states, once at setup."""
    events = async_capture_events(hass, "test_success")
    hass.states.async_set("input_text.hook", "first")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "hook",
                "alias": "hook",
                "trigger": {
                    "platform": "webhook",
                    "webhook_id": "webhook-{{ states('input_text.hook') }}",
                    "local_only": True,
                },
                "action": {"event": "test_success"},
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post("/api/webhook/webhook-first")
    await client.post("/api/webhook/webhook-other")
    await hass.async_block_till_done()

    assert len(events) == 1

    # The webhook ID is only rendered when the trigger is set up, so a state
    # change doesn't move the webhook
    hass.states.async_set("input_text.hook", "second")
    await hass.async_block_till_done()

    await client.post("/api/webhook/webhook-first")
    await client.post("/api/webhook/webhook-second")
    await hass.async_block_till_done()

    assert len(events) == 2
    assert "webhook-first" in hass.data[DOMAIN]
    assert "webhook-second" not in hass.data[DOMAIN]

    # Setting up the trigger again renders the new webhook ID
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.hook"}, blocking=True
    )
    await hass.services.async_call(
        "automation", "turn_on", {"entity_id": "automation.hook"}, blocking=True
    )
    await hass.async_block_till_done()

    assert "webhook-first" not in hass.data[DOMAIN]
    assert "webhook-second" in hass.data[DOMAIN]

    await client.post("/api/webhook/webhook-first")
    await client.post("/api/webhook/webhook-second")
    await hass.async_block_till_done()

    assert len(events) == 3


async def test_webhook_template_hash(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test a template webhook ID can use hash functions."""
    events = async_capture_events(hass, "test_success")
    webhook_id = hashlib.sha256(b"my-hook").hexdigest()

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "webhook",
                    "webhook_id": "{{ sha256('my-hook') }}",
                    "local_only": True,
                },
                "action": {"event": "test_success"},
            }
        },
    )
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    await client.post(f"/api/webhook/{webhook_id}")
    await hass.async_block_till_done()

    assert len(events) == 1


async def test_webhook_template_wait_for_trigger(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test a template webhook ID in a wait is rendered with variables and states."""
    events = async_capture_events(hass, "test_success")
    hass.states.async_set("input_text.hook", "state")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"platform": "event", "event_type": "test_start"},
                "action": [
                    {"variables": {"prefix": "{{ trigger.event.data.prefix }}"}},
                    {
                        "wait_for_trigger": {
                            "platform": "webhook",
                            "webhook_id": (
                                "{{ prefix }}-{{ states('input_text.hook') }}"
                            ),
                            "local_only": True,
                        },
                    },
                    {
                        "event": "test_success",
                        "event_data": {"webhook_id": "{{ wait.trigger.webhook_id }}"},
                    },
                ],
            }
        },
    )
    await hass.async_block_till_done()

    async def webhook_registered() -> None:
        while "run-state" not in hass.data.get(DOMAIN, {}):
            await asyncio.sleep(0)

    # Can't block till done while the action is waiting
    hass.bus.async_fire("test_start", {"prefix": "run"})
    await asyncio.wait_for(webhook_registered(), 1)

    client = await hass_client_no_auth()

    await client.post("/api/webhook/run-state")
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["webhook_id"] == "run-state"
    assert "run-state" not in hass.data[DOMAIN]


async def test_webhook_query_json_header_no_payload(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test requests with application/json header but no payload."""
    events = async_capture_events(hass, "test_success")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "webhook",
                    "webhook_id": "no_payload_webhook",
                    "local_only": True,
                    "allowed_methods": ["GET", "POST"],
                },
                "action": {
                    "event": "test_success",
                },
            }
        },
    )
    await hass.async_block_till_done()
    client = await hass_client_no_auth()

    # GET
    response = await client.get(
        "/api/webhook/no_payload_webhook", headers={"Content-Type": "application/json"}
    )
    await hass.async_block_till_done()
    assert response.status == 200

    # POST
    response = await client.post(
        "/api/webhook/no_payload_webhook", headers={"Content-Type": "application/json"}
    )
    await hass.async_block_till_done()
    assert response.status == 200

    assert len(events) == 2
