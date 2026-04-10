"""Notify platform tests for mobile_app."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.mobile_app.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockUser
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
async def setup_push_receiver(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, hass_admin_user: MockUser
) -> None:
    """Fixture that sets up a mocked push receiver."""
    push_url = "https://mobile-push.home-assistant.dev/push"

    now = datetime.now() + timedelta(hours=24)
    iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    aioclient_mock.post(
        push_url,
        json={
            "rateLimits": {
                "attempts": 1,
                "successful": 1,
                "errors": 0,
                "total": 1,
                "maximum": 150,
                "remaining": 149,
                "resetsAt": iso_time,
            }
        },
    )

    entry = MockConfigEntry(
        data={
            "app_data": {"push_token": "PUSH_TOKEN", "push_url": push_url},
            "app_id": "io.homeassistant.mobile_app",
            "app_name": "mobile_app tests",
            "app_version": "1.0",
            "device_id": "4d5e6f",
            "device_name": "Test",
            "manufacturer": "Home Assistant",
            "model": "mobile_app",
            "os_name": "Linux",
            "os_version": "5.0.6",
            "secret": "123abc",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "mock-webhook_id",
        },
        domain=DOMAIN,
        source="registration",
        title="mobile_app test entry",
        version=1,
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    loaded_late_entry = MockConfigEntry(
        data={
            "app_data": {"push_token": "PUSH_TOKEN2", "push_url": f"{push_url}2"},
            "app_id": "io.homeassistant.mobile_app",
            "app_name": "mobile_app tests",
            "app_version": "1.0",
            "device_id": "4d5e6f2",
            "device_name": "Loaded Late",
            "manufacturer": "Home Assistant",
            "model": "mobile_app",
            "os_name": "Linux",
            "os_version": "5.0.6",
            "secret": "123abc2",
            "supports_encryption": False,
            "user_id": "1a2b3c2",
            "webhook_id": "webhook_id_2",
        },
        domain=DOMAIN,
        source="registration",
        title="mobile_app 2 test entry",
        version=1,
    )
    loaded_late_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(loaded_late_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("notify", "mobile_app_loaded_late")

    assert await hass.config_entries.async_remove(loaded_late_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("notify", "mobile_app_test")
    assert not hass.services.has_service("notify", "mobile_app_loaded_late")

    loaded_late_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(loaded_late_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("notify", "mobile_app_test")
    assert hass.services.has_service("notify", "mobile_app_loaded_late")


@pytest.fixture
async def setup_websocket_channel_only_push(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Set up local push."""
    entry = MockConfigEntry(
        data={
            "app_data": {"push_websocket_channel": True},
            "app_id": "io.homeassistant.mobile_app",
            "app_name": "mobile_app tests",
            "app_version": "1.0",
            "device_id": "websocket-push-device-id",
            "device_name": "Websocket Push Name",
            "manufacturer": "Home Assistant",
            "model": "mobile_app",
            "os_name": "Linux",
            "os_version": "5.0.6",
            "secret": "123abc2",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "websocket-push-webhook-id",
        },
        domain=DOMAIN,
        source="registration",
        title="websocket push test entry",
        version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("notify", "mobile_app_websocket_push_name")


async def test_notify_works(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_push_receiver
) -> None:
    """Test notify works."""
    assert hass.services.has_service("notify", "mobile_app_test") is True
    await hass.services.async_call(
        "notify",
        "mobile_app_test",
        {
            "message": "Hello world",
            "title": "Demo",
            "target": ["mock-webhook_id"],
            "data": {"field1": "value1"},
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]

    assert call_json["push_token"] == "PUSH_TOKEN"
    assert call_json["message"] == "Hello world"
    assert call_json["title"] == "Demo"
    assert call_json["data"] == {"field1": "value1"}
    assert call_json["registration_info"]["app_id"] == "io.homeassistant.mobile_app"
    assert call_json["registration_info"]["app_version"] == "1.0"
    assert call_json["registration_info"]["webhook_id"] == "mock-webhook_id"


async def test_notify_ws_works(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_push_receiver,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test notify works."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "mock-webhook_id",
        }
    )

    sub_result = await client.receive_json()
    assert sub_result["success"]

    # Subscribe twice, it should forward all messages to 2nd subscription
    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "mock-webhook_id",
        }
    )

    sub_result = await client.receive_json()
    assert sub_result["success"]
    new_sub_id = sub_result["id"]

    await hass.services.async_call(
        "notify", "mobile_app_test", {"message": "Hello world"}, blocking=True
    )

    assert len(aioclient_mock.mock_calls) == 0

    msg_result = await client.receive_json()
    assert msg_result["event"] == {"message": "Hello world"}
    assert msg_result["id"] == new_sub_id  # This is the new subscription

    # Unsubscribe, now it should go over http
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": new_sub_id,
        }
    )
    sub_result = await client.receive_json()
    assert sub_result["success"]

    await hass.services.async_call(
        "notify", "mobile_app_test", {"message": "Hello world 2"}, blocking=True
    )

    assert len(aioclient_mock.mock_calls) == 1

    # Test non-existing webhook ID
    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "non-existing",
        }
    )
    sub_result = await client.receive_json()
    assert not sub_result["success"]
    assert sub_result["error"] == {
        "code": "not_found",
        "message": "Webhook ID not found",
    }

    # Test webhook ID linked to other user
    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "webhook_id_2",
        }
    )
    sub_result = await client.receive_json()
    assert not sub_result["success"]
    assert sub_result["error"] == {
        "code": "unauthorized",
        "message": "User not linked to this webhook ID",
    }


async def test_notify_ws_confirming_works(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_push_receiver,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test notify confirming works."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "mock-webhook_id",
            "support_confirm": True,
        }
    )

    sub_result = await client.receive_json()
    assert sub_result["success"]
    sub_id = sub_result["id"]

    # Sent a message that will be delivered locally
    await hass.services.async_call(
        "notify", "mobile_app_test", {"message": "Hello world"}, blocking=True
    )

    msg_result = await client.receive_json()
    confirm_id = msg_result["event"].pop("hass_confirm_id")
    assert confirm_id is not None
    assert msg_result["event"] == {"message": "Hello world"}

    # Try to confirm with incorrect confirm ID
    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_confirm",
            "webhook_id": "mock-webhook_id",
            "confirm_id": "incorrect-confirm-id",
        }
    )

    result = await client.receive_json()
    assert not result["success"]
    assert result["error"] == {
        "code": "not_found",
        "message": "Push notification channel not found",
    }

    # Confirm with correct confirm ID
    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_confirm",
            "webhook_id": "mock-webhook_id",
            "confirm_id": confirm_id,
        }
    )

    result = await client.receive_json()
    assert result["success"]

    # Drop local push channel and try to confirm another message
    await client.send_json_auto_id(
        {
            "type": "unsubscribe_events",
            "subscription": sub_id,
        }
    )
    sub_result = await client.receive_json()
    assert sub_result["success"]

    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_confirm",
            "webhook_id": "mock-webhook_id",
            "confirm_id": confirm_id,
        }
    )

    result = await client.receive_json()
    assert not result["success"]
    assert result["error"] == {
        "code": "not_found",
        "message": "Push notification channel not found",
    }


async def test_notify_ws_not_confirming(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_push_receiver,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we go via cloud when failed to confirm."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "mock-webhook_id",
            "support_confirm": True,
        }
    )

    sub_result = await client.receive_json()
    assert sub_result["success"]

    await hass.services.async_call(
        "notify", "mobile_app_test", {"message": "Hello world 1"}, blocking=True
    )

    with patch(
        "homeassistant.components.mobile_app.push_notification.PUSH_CONFIRM_TIMEOUT", 0
    ):
        await hass.services.async_call(
            "notify", "mobile_app_test", {"message": "Hello world 2"}, blocking=True
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # When we fail, all unconfirmed ones and failed one are sent via cloud
    assert len(aioclient_mock.mock_calls) == 2

    # All future ones also go via cloud
    await hass.services.async_call(
        "notify", "mobile_app_test", {"message": "Hello world 3"}, blocking=True
    )

    assert len(aioclient_mock.mock_calls) == 3


async def test_local_push_only(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_websocket_channel_only_push,
) -> None:
    """Test a local only push registration."""
    with pytest.raises(
        HomeAssistantError,
        match=r"Device.*websocket-push-webhook-id.*not connected to local push notifications",
    ):
        await hass.services.async_call(
            "notify",
            "mobile_app_websocket_push_name",
            {"message": "Not connected"},
            blocking=True,
        )

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "websocket-push-webhook-id",
        }
    )

    sub_result = await client.receive_json()
    assert sub_result["success"]
    sub_id = sub_result["id"]

    await hass.services.async_call(
        "notify",
        "mobile_app_websocket_push_name",
        {"message": "Hello world 1"},
        blocking=True,
    )

    msg = await client.receive_json()
    assert msg["id"] == sub_id
    assert msg["type"] == "event"
    assert msg["event"] == {"message": "Hello world 1"}


@pytest.mark.parametrize(
    "target", [["webhook_id_2", "mock-webhook_id", "websocket-push-webhook-id"], None]
)
async def test_notify_multiple_targets(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_push_receiver,
    setup_websocket_channel_only_push,
    target: list[str] | None,
) -> None:
    """Test notify to multiple targets.

    Messages will be sent to three targerts, one (with webhook id `webhook_id_2`) will be remote target
    and will send the notification via HTTP request, the other two (`mock-webhook_id` and`websocket-push-webhook-id`)
    will be local push only and will be sent via websocket.
    """

    # Setup mock for non-local push notification target
    # with webhook_id "webhook_id_2"
    aioclient_mock.post(
        "https://mobile-push.home-assistant.dev/push2",
        json={
            "rateLimits": {
                "attempts": 1,
                "successful": 1,
                "errors": 0,
                "total": 1,
                "maximum": 150,
                "remaining": 149,
                "resetsAt": (datetime.now() + timedelta(hours=24)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
        },
    )

    client = await hass_ws_client(hass)

    # Setup local push notification channels
    local_push_sub_ids = []
    for webhook_id in ("mock-webhook_id", "websocket-push-webhook-id"):
        await client.send_json_auto_id(
            {
                "type": "mobile_app/push_notification_channel",
                "webhook_id": webhook_id,
            }
        )
        sub_result = await client.receive_json()
        assert sub_result["success"]
        local_push_sub_ids.append(sub_result["id"])

    await hass.services.async_call(
        "notify",
        "notify",
        {
            "message": "Hello world",
            "target": target,
        },
        blocking=True,
    )

    # Assert that the notification has been sent to the non-local push notification target
    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls
    call_json = call[0][2]
    assert call_json["push_token"] == "PUSH_TOKEN2"
    assert call_json["message"] == "Hello world"
    assert call_json["registration_info"]["app_id"] == "io.homeassistant.mobile_app"
    assert call_json["registration_info"]["app_version"] == "1.0"
    assert call_json["registration_info"]["webhook_id"] == "webhook_id_2"

    # Assert that the notification has been sent to the two local push notification targets
    for sub_id in local_push_sub_ids:
        msg_result = await client.receive_json()
        assert msg_result["event"] == {"message": "Hello world"}
        msg_id = msg_result["id"]
        assert msg_id == sub_id


@pytest.mark.parametrize(
    "target", [["webhook_id_2", "mock-webhook_id", "websocket-push-webhook-id"], None]
)
async def test_notify_multiple_targets_if_any_disconnected(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_push_receiver,
    setup_websocket_channel_only_push,
    target: list[str] | None,
) -> None:
    """Notify works with disconnected targets.

    Test that although one target is disconnected,
    notify still works to other targets and the exception is still raised.
    """
    # Setup mock for non-local push notification target
    # with webhook_id "webhook_id_2"
    aioclient_mock.post(
        "https://mobile-push.home-assistant.dev/push2",
        json={
            "rateLimits": {
                "attempts": 1,
                "successful": 1,
                "errors": 0,
                "total": 1,
                "maximum": 150,
                "remaining": 149,
                "resetsAt": (datetime.now() + timedelta(hours=24)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
        },
    )

    client = await hass_ws_client(hass)

    # Setup the local push notification channel
    await client.send_json_auto_id(
        {
            "type": "mobile_app/push_notification_channel",
            "webhook_id": "mock-webhook_id",
        }
    )
    sub_result = await client.receive_json()
    assert sub_result["success"]
    sub_id = sub_result["id"]

    with pytest.raises(
        HomeAssistantError,
        match=r".*websocket-push-webhook-id.*not connected to local push notifications",
    ):
        await hass.services.async_call(
            "notify",
            "notify",
            {
                "message": "Hello world",
                "target": target,
            },
            blocking=True,
        )

    # Assert that the notification has been sent to the non-local push notification target
    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls
    call_json = call[0][2]
    assert call_json["push_token"] == "PUSH_TOKEN2"
    assert call_json["message"] == "Hello world"
    assert call_json["registration_info"]["app_id"] == "io.homeassistant.mobile_app"
    assert call_json["registration_info"]["app_version"] == "1.0"
    assert call_json["registration_info"]["webhook_id"] == "webhook_id_2"

    # Assert that the notification has been sent to the local
    # push notification target that has been setup
    msg_result = await client.receive_json()
    assert msg_result["event"] == {"message": "Hello world"}
    assert msg_result["id"] == sub_id

    # Check that there are no more messages to receive (timeout expected)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client.receive_json(), timeout=0.1)
