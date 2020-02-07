"""Test the cloud.iot module."""
from unittest.mock import MagicMock, patch

from aiohttp import web
import pytest

from homeassistant.components.cloud import DOMAIN
from homeassistant.components.cloud.client import CloudClient
from homeassistant.components.cloud.const import PREF_ENABLE_ALEXA, PREF_ENABLE_GOOGLE
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from . import mock_cloud, mock_cloud_prefs

from tests.common import mock_coro
from tests.components.alexa import test_smart_home as test_alexa


@pytest.fixture
def mock_cloud_inst():
    """Mock cloud class."""
    return MagicMock(subscription_expired=False)


async def test_handler_alexa(hass):
    """Test handler Alexa."""
    hass.states.async_set("switch.test", "on", {"friendly_name": "Test switch"})
    hass.states.async_set("switch.test2", "on", {"friendly_name": "Test switch 2"})

    await mock_cloud(
        hass,
        {
            "alexa": {
                "filter": {"exclude_entities": "switch.test2"},
                "entity_config": {
                    "switch.test": {
                        "name": "Config name",
                        "description": "Config description",
                        "display_categories": "LIGHT",
                    }
                },
            }
        },
    )

    mock_cloud_prefs(hass)
    cloud = hass.data["cloud"]

    resp = await cloud.client.async_alexa_message(
        test_alexa.get_new_request("Alexa.Discovery", "Discover")
    )

    endpoints = resp["event"]["payload"]["endpoints"]

    assert len(endpoints) == 1
    device = endpoints[0]

    assert device["description"] == "Config description via Home Assistant"
    assert device["friendlyName"] == "Config name"
    assert device["displayCategories"] == ["LIGHT"]
    assert device["manufacturerName"] == "Home Assistant"


async def test_handler_alexa_disabled(hass, mock_cloud_fixture):
    """Test handler Alexa when user has disabled it."""
    mock_cloud_fixture._prefs[PREF_ENABLE_ALEXA] = False
    cloud = hass.data["cloud"]

    resp = await cloud.client.async_alexa_message(
        test_alexa.get_new_request("Alexa.Discovery", "Discover")
    )

    assert resp["event"]["header"]["namespace"] == "Alexa"
    assert resp["event"]["header"]["name"] == "ErrorResponse"
    assert resp["event"]["payload"]["type"] == "BRIDGE_UNREACHABLE"


async def test_handler_google_actions(hass):
    """Test handler Google Actions."""
    hass.states.async_set("switch.test", "on", {"friendly_name": "Test switch"})
    hass.states.async_set("switch.test2", "on", {"friendly_name": "Test switch 2"})
    hass.states.async_set("group.all_locks", "on", {"friendly_name": "Evil locks"})

    await mock_cloud(
        hass,
        {
            "google_actions": {
                "filter": {"exclude_entities": "switch.test2"},
                "entity_config": {
                    "switch.test": {
                        "name": "Config name",
                        "aliases": "Config alias",
                        "room": "living room",
                    }
                },
            }
        },
    )

    mock_cloud_prefs(hass)
    cloud = hass.data["cloud"]

    reqid = "5711642932632160983"
    data = {"requestId": reqid, "inputs": [{"intent": "action.devices.SYNC"}]}

    with patch(
        "hass_nabucasa.Cloud._decode_claims",
        return_value={"cognito:username": "myUserName"},
    ):
        await cloud.client.get_google_config()
        resp = await cloud.client.async_google_message(data)

    assert resp["requestId"] == reqid
    payload = resp["payload"]

    assert payload["agentUserId"] == "myUserName"

    devices = payload["devices"]
    assert len(devices) == 1

    device = devices[0]
    assert device["id"] == "switch.test"
    assert device["name"]["name"] == "Config name"
    assert device["name"]["nicknames"] == ["Config name", "Config alias"]
    assert device["type"] == "action.devices.types.SWITCH"
    assert device["roomHint"] == "living room"


async def test_handler_google_actions_disabled(hass, mock_cloud_fixture):
    """Test handler Google Actions when user has disabled it."""
    mock_cloud_fixture._prefs[PREF_ENABLE_GOOGLE] = False

    with patch("hass_nabucasa.Cloud.start", return_value=mock_coro()):
        assert await async_setup_component(hass, "cloud", {})

    reqid = "5711642932632160983"
    data = {"requestId": reqid, "inputs": [{"intent": "action.devices.SYNC"}]}

    cloud = hass.data["cloud"]
    resp = await cloud.client.async_google_message(data)

    assert resp["requestId"] == reqid
    assert resp["payload"]["errorCode"] == "deviceTurnedOff"


async def test_webhook_msg(hass):
    """Test webhook msg."""
    with patch("hass_nabucasa.Cloud.start", return_value=mock_coro()):
        setup = await async_setup_component(hass, "cloud", {"cloud": {}})
        assert setup
    cloud = hass.data["cloud"]

    await cloud.client.prefs.async_initialize()
    await cloud.client.prefs.async_update(
        cloudhooks={
            "hello": {"webhook_id": "mock-webhook-id", "cloudhook_id": "mock-cloud-id"}
        }
    )

    received = []

    async def handler(hass, webhook_id, request):
        """Handle a webhook."""
        received.append(request)
        return web.json_response({"from": "handler"})

    hass.components.webhook.async_register("test", "Test", "mock-webhook-id", handler)

    response = await cloud.client.async_webhook_message(
        {
            "cloudhook_id": "mock-cloud-id",
            "body": '{"hello": "world"}',
            "headers": {"content-type": "application/json"},
            "method": "POST",
            "query": None,
        }
    )

    assert response == {
        "status": 200,
        "body": '{"from": "handler"}',
        "headers": {"Content-Type": "application/json"},
    }

    assert len(received) == 1
    assert await received[0].json() == {"hello": "world"}


async def test_google_config_expose_entity(hass, mock_cloud_setup, mock_cloud_login):
    """Test Google config exposing entity method uses latest config."""
    cloud_client = hass.data[DOMAIN].client
    state = State("light.kitchen", "on")
    gconf = await cloud_client.get_google_config()

    assert gconf.should_expose(state)

    await cloud_client.prefs.async_update_google_entity_config(
        entity_id="light.kitchen", should_expose=False
    )

    assert not gconf.should_expose(state)


async def test_google_config_should_2fa(hass, mock_cloud_setup, mock_cloud_login):
    """Test Google config disabling 2FA method uses latest config."""
    cloud_client = hass.data[DOMAIN].client
    gconf = await cloud_client.get_google_config()
    state = State("light.kitchen", "on")

    assert gconf.should_2fa(state)

    await cloud_client.prefs.async_update_google_entity_config(
        entity_id="light.kitchen", disable_2fa=True
    )

    assert not gconf.should_2fa(state)


async def test_set_username(hass):
    """Test we set username during login."""
    prefs = MagicMock(
        alexa_enabled=False,
        google_enabled=False,
        async_set_username=MagicMock(return_value=mock_coro()),
    )
    client = CloudClient(hass, prefs, None, {}, {})
    client.cloud = MagicMock(is_logged_in=True, username="mock-username")
    await client.logged_in()

    assert len(prefs.async_set_username.mock_calls) == 1
    assert prefs.async_set_username.mock_calls[0][1][0] == "mock-username"
