"""Test the cloud.iot module."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import aiohttp
from aiohttp import web
import pytest

from homeassistant.components.cloud import DOMAIN
from homeassistant.components.cloud.client import CloudClient
from homeassistant.components.cloud.const import (
    PREF_ALEXA_REPORT_STATE,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_GOOGLE,
)
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    ExposedEntities,
    async_expose_entity,
)
from homeassistant.const import CONTENT_TYPE_JSON, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import mock_cloud, mock_cloud_prefs

from tests.common import async_fire_time_changed
from tests.components.alexa import test_smart_home as test_alexa


@pytest.fixture
def mock_cloud_inst():
    """Mock cloud class."""
    return MagicMock(subscription_expired=False)


async def test_handler_alexa(hass: HomeAssistant) -> None:
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

    mock_cloud_prefs(hass, {PREF_ALEXA_REPORT_STATE: False})
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


async def test_handler_alexa_disabled(hass: HomeAssistant, mock_cloud_fixture) -> None:
    """Test handler Alexa when user has disabled it."""
    mock_cloud_fixture._prefs[PREF_ENABLE_ALEXA] = False
    cloud = hass.data["cloud"]

    resp = await cloud.client.async_alexa_message(
        test_alexa.get_new_request("Alexa.Discovery", "Discover")
    )

    assert resp["event"]["header"]["namespace"] == "Alexa"
    assert resp["event"]["header"]["name"] == "ErrorResponse"
    assert resp["event"]["payload"]["type"] == "BRIDGE_UNREACHABLE"


async def test_handler_google_actions(hass: HomeAssistant) -> None:
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


@pytest.mark.parametrize(
    ("intent", "response_payload"),
    [
        ("action.devices.SYNC", {"agentUserId": "myUserName", "devices": []}),
        ("action.devices.QUERY", {"errorCode": "deviceTurnedOff"}),
    ],
)
async def test_handler_google_actions_disabled(
    hass: HomeAssistant, mock_cloud_fixture, intent, response_payload
) -> None:
    """Test handler Google Actions when user has disabled it."""
    mock_cloud_fixture._prefs[PREF_ENABLE_GOOGLE] = False

    with patch("hass_nabucasa.Cloud.initialize"):
        assert await async_setup_component(hass, "cloud", {})

    reqid = "5711642932632160983"
    data = {"requestId": reqid, "inputs": [{"intent": intent}]}

    cloud = hass.data["cloud"]
    with patch(
        "hass_nabucasa.Cloud._decode_claims",
        return_value={"cognito:username": "myUserName"},
    ):
        resp = await cloud.client.async_google_message(data)

    assert resp["requestId"] == reqid
    assert resp["payload"] == response_payload


async def test_webhook_msg(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test webhook msg."""
    with patch("hass_nabucasa.Cloud.initialize"):
        setup = await async_setup_component(hass, "cloud", {"cloud": {}})
        assert setup
    cloud = hass.data["cloud"]

    await cloud.client.prefs.async_initialize()
    await cloud.client.prefs.async_update(
        cloudhooks={
            "mock-webhook-id": {
                "webhook_id": "mock-webhook-id",
                "cloudhook_id": "mock-cloud-id",
            },
            "no-longere-existing": {
                "webhook_id": "no-longere-existing",
                "cloudhook_id": "mock-nonexisting-id",
            },
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
            "headers": {"content-type": CONTENT_TYPE_JSON},
            "method": "POST",
            "query": None,
        }
    )

    assert response == {
        "status": 200,
        "body": '{"from": "handler"}',
        "headers": {"Content-Type": CONTENT_TYPE_JSON},
    }

    assert len(received) == 1
    assert await received[0].json() == {"hello": "world"}

    # Non existing webhook
    caplog.clear()

    response = await cloud.client.async_webhook_message(
        {
            "cloudhook_id": "mock-nonexisting-id",
            "body": '{"nonexisting": "payload"}',
            "headers": {"content-type": CONTENT_TYPE_JSON},
            "method": "POST",
            "query": None,
        }
    )

    assert response == {
        "status": 200,
        "body": None,
        "headers": {"Content-Type": "application/octet-stream"},
    }

    assert (
        "Received message for unregistered webhook no-longere-existing from cloud"
        in caplog.text
    )
    assert '{"nonexisting": "payload"}' in caplog.text


async def test_google_config_expose_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_cloud_setup,
    mock_cloud_login,
) -> None:
    """Test Google config exposing entity method uses latest config."""

    # Enable exposing new entities to Google
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities("cloud.google_assistant", True)

    # Register a light entity
    entity_entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )

    cloud_client = hass.data[DOMAIN].client
    state = State(entity_entry.entity_id, "on")
    gconf = await cloud_client.get_google_config()

    assert gconf.should_expose(state)

    async_expose_entity(hass, "cloud.google_assistant", entity_entry.entity_id, False)

    assert not gconf.should_expose(state)


async def test_google_config_should_2fa(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_cloud_setup,
    mock_cloud_login,
) -> None:
    """Test Google config disabling 2FA method uses latest config."""

    # Register a light entity
    entity_entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )

    cloud_client = hass.data[DOMAIN].client
    gconf = await cloud_client.get_google_config()
    state = State(entity_entry.entity_id, "on")

    assert gconf.should_2fa(state)

    entity_registry.async_update_entity_options(
        entity_entry.entity_id, "cloud.google_assistant", {"disable_2fa": True}
    )

    assert not gconf.should_2fa(state)


async def test_set_username(hass: HomeAssistant) -> None:
    """Test we set username during login."""
    prefs = MagicMock(
        alexa_enabled=False,
        google_enabled=False,
        async_set_username=AsyncMock(return_value=None),
    )
    client = CloudClient(hass, prefs, None, {}, {})
    client.cloud = MagicMock(is_logged_in=True, username="mock-username")
    await client.cloud_connected()

    assert len(prefs.async_set_username.mock_calls) == 1
    assert prefs.async_set_username.mock_calls[0][1][0] == "mock-username"


async def test_login_recovers_bad_internet(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test Alexa can recover bad auth."""
    prefs = Mock(
        alexa_enabled=True,
        google_enabled=False,
        async_set_username=AsyncMock(return_value=None),
    )
    client = CloudClient(hass, prefs, None, {}, {})
    client.cloud = Mock()
    client._alexa_config = Mock(
        async_enable_proactive_mode=Mock(side_effect=aiohttp.ClientError)
    )
    await client.cloud_connected()
    assert len(client._alexa_config.async_enable_proactive_mode.mock_calls) == 1
    assert "Unable to activate Alexa Report State" in caplog.text

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert len(client._alexa_config.async_enable_proactive_mode.mock_calls) == 2


async def test_system_msg(hass: HomeAssistant) -> None:
    """Test system msg."""
    with patch("hass_nabucasa.Cloud.initialize"):
        setup = await async_setup_component(hass, "cloud", {"cloud": {}})
        assert setup
    cloud = hass.data["cloud"]

    assert cloud.client.relayer_region is None

    response = await cloud.client.async_system_message(
        {
            "region": "xx-earth-616",
        }
    )

    assert response is None
    assert cloud.client.relayer_region == "xx-earth-616"


async def test_cloud_connection_info(hass: HomeAssistant) -> None:
    """Test connection info msg."""
    with patch("hass_nabucasa.Cloud.initialize"), patch(
        "uuid.UUID.hex", new_callable=PropertyMock
    ) as hexmock:
        hexmock.return_value = "12345678901234567890"
        setup = await async_setup_component(hass, "cloud", {"cloud": {}})
        assert setup
    cloud = hass.data["cloud"]

    response = await cloud.client.async_cloud_connection_info({})

    assert response == {
        "remote": {
            "connected": False,
            "enabled": False,
            "instance_domain": None,
            "alias": None,
        },
        "version": HA_VERSION,
        "instance_id": "12345678901234567890",
    }
