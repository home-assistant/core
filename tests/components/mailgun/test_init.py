"""Test the init file of Mailgun."""
import hashlib
import hmac

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import mailgun, webhook
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

API_KEY = "abc123"


@pytest.fixture
async def http_client(hass, hass_client_no_auth):
    """Initialize a Home Assistant Server for testing this module."""
    await async_setup_component(hass, webhook.DOMAIN, {})
    return await hass_client_no_auth()


@pytest.fixture
async def webhook_id_with_api_key(hass):
    """Initialize the Mailgun component and get the webhook_id."""
    await async_setup_component(
        hass,
        mailgun.DOMAIN,
        {mailgun.DOMAIN: {CONF_API_KEY: API_KEY, CONF_DOMAIN: "example.com"}},
    )

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    result = await hass.config_entries.flow.async_init(
        "mailgun", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    return result["result"].data["webhook_id"]


@pytest.fixture
async def webhook_id_without_api_key(hass):
    """Initialize the Mailgun component and get the webhook_id w/o API key."""
    await async_setup_component(hass, mailgun.DOMAIN, {})

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    result = await hass.config_entries.flow.async_init(
        "mailgun", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    return result["result"].data["webhook_id"]


@pytest.fixture
async def mailgun_events(hass):
    """Return a list of mailgun_events triggered."""
    events = []

    @callback
    def handle_event(event):
        """Handle Mailgun event."""
        events.append(event)

    hass.bus.async_listen(mailgun.MESSAGE_RECEIVED, handle_event)

    return events


async def test_mailgun_webhook_with_missing_signature(
    http_client, webhook_id_with_api_key, mailgun_events
):
    """Test that webhook doesn't trigger an event without a signature."""
    event_count = len(mailgun_events)

    await http_client.post(
        f"/api/webhook/{webhook_id_with_api_key}",
        json={"hello": "mailgun", "signature": {}},
    )

    assert len(mailgun_events) == event_count

    await http_client.post(
        f"/api/webhook/{webhook_id_with_api_key}", json={"hello": "mailgun"}
    )

    assert len(mailgun_events) == event_count


async def test_mailgun_webhook_with_different_api_key(
    http_client, webhook_id_with_api_key, mailgun_events
):
    """Test that webhook doesn't trigger an event with a wrong signature."""
    timestamp = "1529006854"
    token = "a8ce0edb2dd8301dee6c2405235584e45aa91d1e9f979f3de0"

    event_count = len(mailgun_events)

    await http_client.post(
        f"/api/webhook/{webhook_id_with_api_key}",
        json={
            "hello": "mailgun",
            "signature": {
                "signature": hmac.new(
                    key=b"random_api_key",
                    msg=bytes(f"{timestamp}{token}", "utf-8"),
                    digestmod=hashlib.sha256,
                ).hexdigest(),
                "timestamp": timestamp,
                "token": token,
            },
        },
    )

    assert len(mailgun_events) == event_count


async def test_mailgun_webhook_event_with_correct_api_key(
    http_client, webhook_id_with_api_key, mailgun_events
):
    """Test that webhook triggers an event after validating a signature."""
    timestamp = "1529006854"
    token = "a8ce0edb2dd8301dee6c2405235584e45aa91d1e9f979f3de0"

    event_count = len(mailgun_events)

    await http_client.post(
        f"/api/webhook/{webhook_id_with_api_key}",
        json={
            "hello": "mailgun",
            "signature": {
                "signature": hmac.new(
                    key=bytes(API_KEY, "utf-8"),
                    msg=bytes(f"{timestamp}{token}", "utf-8"),
                    digestmod=hashlib.sha256,
                ).hexdigest(),
                "timestamp": timestamp,
                "token": token,
            },
        },
    )

    assert len(mailgun_events) == event_count + 1
    assert mailgun_events[-1].data["webhook_id"] == webhook_id_with_api_key
    assert mailgun_events[-1].data["hello"] == "mailgun"


async def test_mailgun_webhook_with_missing_signature_without_api_key(
    http_client, webhook_id_without_api_key, mailgun_events
):
    """Test that webhook triggers an event without a signature w/o API key."""
    event_count = len(mailgun_events)

    await http_client.post(
        f"/api/webhook/{webhook_id_without_api_key}",
        json={"hello": "mailgun", "signature": {}},
    )

    assert len(mailgun_events) == event_count + 1
    assert mailgun_events[-1].data["webhook_id"] == webhook_id_without_api_key
    assert mailgun_events[-1].data["hello"] == "mailgun"

    await http_client.post(
        f"/api/webhook/{webhook_id_without_api_key}", json={"hello": "mailgun"}
    )

    assert len(mailgun_events) == event_count + 1
    assert mailgun_events[-1].data["webhook_id"] == webhook_id_without_api_key
    assert mailgun_events[-1].data["hello"] == "mailgun"


async def test_mailgun_webhook_event_without_an_api_key(
    http_client, webhook_id_without_api_key, mailgun_events
):
    """Test that webhook triggers an event if there is no api key."""
    timestamp = "1529006854"
    token = "a8ce0edb2dd8301dee6c2405235584e45aa91d1e9f979f3de0"

    event_count = len(mailgun_events)

    await http_client.post(
        f"/api/webhook/{webhook_id_without_api_key}",
        json={
            "hello": "mailgun",
            "signature": {
                "signature": hmac.new(
                    key=bytes(API_KEY, "utf-8"),
                    msg=bytes(f"{timestamp}{token}", "utf-8"),
                    digestmod=hashlib.sha256,
                ).hexdigest(),
                "timestamp": timestamp,
                "token": token,
            },
        },
    )

    assert len(mailgun_events) == event_count + 1
    assert mailgun_events[-1].data["webhook_id"] == webhook_id_without_api_key
    assert mailgun_events[-1].data["hello"] == "mailgun"
