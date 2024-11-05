"""Test the cloud.iot module."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import aiohttp
from aiohttp import web
from hass_nabucasa.client import RemoteActivationNotAllowed
import pytest

from homeassistant.components import webhook
from homeassistant.components.cloud import DOMAIN
from homeassistant.components.cloud.client import (
    VALID_REPAIR_TRANSLATION_KEYS,
    CloudClient,
)
from homeassistant.components.cloud.const import (
    DATA_CLOUD,
    PREF_ALEXA_REPORT_STATE,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_GOOGLE,
)
from homeassistant.components.cloud.prefs import CloudPreferences
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    async_expose_entity,
)
from homeassistant.const import CONTENT_TYPE_JSON, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import mock_cloud, mock_cloud_prefs

from tests.common import async_fire_time_changed
from tests.components.alexa import test_smart_home as test_alexa


@pytest.fixture
def mock_cloud_inst() -> MagicMock:
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
    cloud = hass.data[DATA_CLOUD]

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


async def test_handler_alexa_disabled(
    hass: HomeAssistant, mock_cloud_fixture: CloudPreferences
) -> None:
    """Test handler Alexa when user has disabled it."""
    mock_cloud_fixture._prefs[PREF_ENABLE_ALEXA] = False
    cloud = hass.data[DATA_CLOUD]

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

    mock_cloud_prefs(hass, {})
    cloud = hass.data[DATA_CLOUD]

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
    hass: HomeAssistant,
    mock_cloud_fixture: CloudPreferences,
    intent: str,
    response_payload: dict[str, Any],
) -> None:
    """Test handler Google Actions when user has disabled it."""
    mock_cloud_fixture._prefs[PREF_ENABLE_GOOGLE] = False

    with patch("hass_nabucasa.Cloud.initialize"):
        assert await async_setup_component(hass, "cloud", {})

    reqid = "5711642932632160983"
    data = {"requestId": reqid, "inputs": [{"intent": intent}]}

    cloud = hass.data[DATA_CLOUD]
    with patch(
        "hass_nabucasa.Cloud._decode_claims",
        return_value={"cognito:username": "myUserName"},
    ):
        resp = await cloud.client.async_google_message(data)

    assert resp["requestId"] == reqid
    assert resp["payload"] == response_payload


async def test_handler_ice_servers(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test handler ICE servers."""
    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()
    # make sure that preferences will not be reset
    await cloud.client.prefs.async_set_username(cloud.username)
    await set_cloud_prefs(
        {
            "alexa_enabled": False,
            "google_enabled": False,
        }
    )

    await cloud.login("test-user", "test-pass")
    await cloud.client.cloud_connected()

    assert cloud.client._cloud_ice_servers_listener is not None
    assert cloud.client._cloud_ice_servers_listener() == "mock-unregister"


async def test_handler_ice_servers_disabled(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test handler ICE servers when user has disabled it."""
    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()
    # make sure that preferences will not be reset
    await cloud.client.prefs.async_set_username(cloud.username)
    await set_cloud_prefs(
        {
            "alexa_enabled": False,
            "google_enabled": False,
        }
    )

    await cloud.login("test-user", "test-pass")
    await cloud.client.cloud_connected()

    await set_cloud_prefs(
        {
            "cloud_ice_servers_enabled": False,
        }
    )

    assert cloud.client._cloud_ice_servers_listener is None


async def test_webhook_msg(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test webhook msg."""
    with patch("hass_nabucasa.Cloud.initialize"):
        setup = await async_setup_component(hass, "cloud", {"cloud": {}})
        assert setup
    cloud = hass.data[DATA_CLOUD]

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

    async def handler(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle a webhook."""
        received.append(request)
        return web.json_response({"from": "handler"})

    webhook.async_register(hass, "test", "Test", "mock-webhook-id", handler)

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


@pytest.mark.usefixtures("mock_cloud_setup", "mock_cloud_login")
async def test_google_config_expose_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Google config exposing entity method uses latest config."""

    # Enable exposing new entities to Google
    exposed_entities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities("cloud.google_assistant", True)

    # Register a light entity
    entity_entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )

    cloud_client = hass.data[DATA_CLOUD].client
    state = State(entity_entry.entity_id, "on")
    gconf = await cloud_client.get_google_config()

    assert gconf.should_expose(state)

    async_expose_entity(hass, "cloud.google_assistant", entity_entry.entity_id, False)

    assert not gconf.should_expose(state)


@pytest.mark.usefixtures("mock_cloud_setup", "mock_cloud_login")
async def test_google_config_should_2fa(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Google config disabling 2FA method uses latest config."""

    # Register a light entity
    entity_entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )

    cloud_client = hass.data[DATA_CLOUD].client
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
    cloud = hass.data[DATA_CLOUD]

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
    with (
        patch("hass_nabucasa.Cloud.initialize"),
        patch("uuid.UUID.hex", new_callable=PropertyMock) as hexmock,
    ):
        hexmock.return_value = "12345678901234567890"
        setup = await async_setup_component(hass, "cloud", {"cloud": {}})
        assert setup
    cloud = hass.data[DATA_CLOUD]

    response = await cloud.client.async_cloud_connection_info({})

    assert response == {
        "instance_id": "12345678901234567890",
        "remote": {
            "alias": None,
            "can_enable": True,
            "connected": False,
            "enabled": False,
            "instance_domain": None,
        },
        "version": HA_VERSION,
    }


@pytest.mark.parametrize(
    "translation_key",
    sorted(VALID_REPAIR_TRANSLATION_KEYS),
)
async def test_async_create_repair_issue_known(
    cloud: MagicMock,
    mock_cloud_setup: None,
    issue_registry: ir.IssueRegistry,
    translation_key: str,
) -> None:
    """Test create repair issue for known repairs."""
    identifier = f"test_identifier_{translation_key}"
    await cloud.client.async_create_repair_issue(
        identifier=identifier,
        translation_key=translation_key,
        placeholders={"custom_domains": "example.com"},
        severity="warning",
    )
    issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=identifier)
    assert issue is not None


async def test_async_create_repair_issue_unknown(
    cloud: MagicMock,
    mock_cloud_setup: None,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test not creating repair issue for unknown repairs."""
    identifier = "abc123"
    with pytest.raises(
        ValueError,
        match="Invalid translation key unknown_translation_key",
    ):
        await cloud.client.async_create_repair_issue(
            identifier=identifier,
            translation_key="unknown_translation_key",
            placeholders={"custom_domains": "example.com"},
            severity="error",
        )
    issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=identifier)
    assert issue is None


async def test_disconnected(hass: HomeAssistant) -> None:
    """Test cleanup when disconnected from the cloud."""
    prefs = MagicMock(
        alexa_enabled=False,
        google_enabled=True,
        async_set_username=AsyncMock(return_value=None),
    )
    client = CloudClient(hass, prefs, None, {}, {})
    client.cloud = MagicMock(is_logged_in=True, username="mock-username")
    client._google_config = Mock()
    client._google_config.async_disable_local_sdk.assert_not_called()

    await client.cloud_disconnected()
    client._google_config.async_disable_local_sdk.assert_called_once_with()


async def test_logged_out(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test cleanup when logged out from the cloud."""

    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")

    alexa_config_mock = Mock(async_enable_proactive_mode=AsyncMock())
    google_config_mock = Mock(async_sync_entities=AsyncMock())
    cloud.client._alexa_config = alexa_config_mock
    cloud.client._google_config = google_config_mock

    await cloud.client.cloud_connected()
    await hass.async_block_till_done()

    assert cloud.client._cloud_ice_servers_listener is not None

    # Simulate logged out
    await cloud.logout()
    await hass.async_block_till_done()

    # Check we clean up Alexa, Google and ICE servers
    assert cloud.client._alexa_config is None
    assert cloud.client._google_config is None
    assert cloud.client._cloud_ice_servers_listener is None
    google_config_mock.async_deinitialize.assert_called_once_with()
    alexa_config_mock.async_deinitialize.assert_called_once_with()


async def test_remote_enable(hass: HomeAssistant) -> None:
    """Test enabling remote UI."""
    prefs = MagicMock(async_update=AsyncMock(return_value=None))
    client = CloudClient(hass, prefs, None, {}, {})
    client.cloud = MagicMock(is_logged_in=True, username="mock-username")

    await client.async_cloud_connect_update(True)
    prefs.async_update.assert_called_once_with(remote_enabled=True)


async def test_remote_enable_not_allowed(hass: HomeAssistant) -> None:
    """Test enabling remote UI."""
    prefs = MagicMock(
        async_update=AsyncMock(return_value=None),
        remote_allow_remote_enable=False,
    )
    client = CloudClient(hass, prefs, None, {}, {})
    client.cloud = MagicMock(is_logged_in=True, username="mock-username")

    with pytest.raises(RemoteActivationNotAllowed):
        await client.async_cloud_connect_update(True)
    prefs.async_update.assert_not_called()
