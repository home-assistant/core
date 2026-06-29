"""Notify platform tests for mobile_app."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from http import HTTPStatus
import logging
from unittest.mock import patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mobile_app.const import (
    DATA_LIVE_ACTIVITY_PENDING_STARTS,
    DATA_LIVE_ACTIVITY_TOKENS,
    DOMAIN,
    LIVE_ACTIVITY_START_COOLDOWN_SECONDS,
)
from homeassistant.components.mobile_app.live_activity.store import clear_start_pending
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, MockUser, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
async def setup_push_receiver(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, hass_admin_user: MockUser
) -> None:
    """Fixture that sets up a mocked push receiver."""
    push_url = "https://mobile-push.home-assistant.dev/push"

    now = dt_util.naive_now() + timedelta(hours=24)
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
async def setup_apple_push_receiver(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, hass_admin_user: MockUser
) -> None:
    """Set up a mocked push receiver on an Apple device for Live Activity tests.

    Live Activity routing only runs for Apple devices, so these tests need the
    receiver registered as one instead of the generic ``setup_push_receiver``.
    """
    push_url = "https://mobile-push.home-assistant.dev/push"

    now = dt_util.naive_now() + timedelta(hours=24)
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
            "device_name": "Apple test device",
            "manufacturer": "Apple",
            "model": "mobile_app",
            "os_name": "iOS",
            "os_version": "5.0.6",
            "secret": "123abc",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "mock-webhook_id",
        },
        domain=DOMAIN,
        source="registration",
        title="mobile_app Apple device test entry",
        version=1,
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


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


@pytest.fixture
async def notify_only() -> AsyncGenerator[None]:
    """Enable only the notify platform."""
    with patch(
        "homeassistant.components.mobile_app.PLATFORMS",
        [Platform.NOTIFY],
    ):
        yield


@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_notify_works(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_push_receiver
) -> None:
    """Test notify works."""

    state = hass.states.get("notify.test")
    assert state
    assert state.state == STATE_UNKNOWN

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

    await hass.async_block_till_done()
    state = hass.states.get("notify.test")
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


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


@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_local_push_only(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup_websocket_channel_only_push,
) -> None:
    """Test a local only push registration."""
    with pytest.raises(
        HomeAssistantError,
        match=(
            r"Device.*websocket-push-webhook-id"
            r".*not connected to local push notifications"
        ),
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

    state = hass.states.get("notify.websocket_push_name")
    assert state
    assert state.state == STATE_UNKNOWN

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

    state = hass.states.get("notify.websocket_push_name")
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


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

    Messages will be sent to three targets, one (with webhook id
    `webhook_id_2`) will be remote target and will send the notification
    via HTTP request, the other two (`mock-webhook_id` and
    `websocket-push-webhook-id`) will be local push only and will be
    sent via websocket.
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
                "resetsAt": (dt_util.naive_now() + timedelta(hours=24)).strftime(
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

    # Assert notification sent to non-local push notification target
    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls
    call_json = call[0][2]
    assert call_json["push_token"] == "PUSH_TOKEN2"
    assert call_json["message"] == "Hello world"
    assert call_json["registration_info"]["app_id"] == "io.homeassistant.mobile_app"
    assert call_json["registration_info"]["app_version"] == "1.0"
    assert call_json["registration_info"]["webhook_id"] == "webhook_id_2"

    # Assert notification sent to the two local push targets
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
                "resetsAt": (dt_util.naive_now() + timedelta(hours=24)).strftime(
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

    # Assert notification sent to non-local push notification target
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


@pytest.mark.usefixtures("notify_only")
async def test_notify_platform(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Mobile app notify platform."""
    config_entry = MockConfigEntry(
        data={
            "app_data": {
                "push_token": "PUSH_TOKEN",
                "push_url": "https://mobile-push.home-assistant.dev/push",
            },
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

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("setup_push_receiver")
@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_send_message(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test sending message via notify.send_message action."""

    state = hass.states.get("notify.test")
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.test",
            ATTR_MESSAGE: "Hello world",
            ATTR_TITLE: "test",
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]

    assert call_json["push_token"] == "PUSH_TOKEN"
    assert call_json["message"] == "Hello world"
    assert call_json["title"] == "test"
    assert call_json["registration_info"]["app_id"] == "io.homeassistant.mobile_app"
    assert call_json["registration_info"]["app_version"] == "1.0"
    assert call_json["registration_info"]["webhook_id"] == "mock-webhook_id"

    state = hass.states.get("notify.test")
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


@pytest.mark.usefixtures("setup_websocket_channel_only_push")
@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_send_message_local_push(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test sending message via notify.send_message action through local push."""
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
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.websocket_push_name",
            ATTR_MESSAGE: "Hello world",
            ATTR_TITLE: "test",
        },
        blocking=True,
    )

    msg = await client.receive_json()
    assert msg["id"] == sub_id
    assert msg["type"] == "event"
    assert msg["event"] == {"message": "Hello world", "title": "test"}

    state = hass.states.get("notify.websocket_push_name")
    assert state
    assert state.state == "1970-01-01T00:00:00+00:00"


@pytest.mark.parametrize(
    ("exc", "status", "error_msg"),
    [
        (
            None,
            HTTPStatus.TOO_MANY_REQUESTS,
            "rate_limit_exceeded_sending_notification",
        ),
        (
            None,
            HTTPStatus.BAD_REQUEST,
            "error_sending_notification",
        ),
        (
            TimeoutError,
            HTTPStatus.OK,
            "timeout_sending_notification",
        ),
        (
            ClientError,
            HTTPStatus.OK,
            "error_sending_notification",
        ),
    ],
)
@pytest.mark.usefixtures("setup_push_receiver")
@pytest.mark.freeze_time("1970-01-01T00:00:00.000Z")
async def test_send_message_exceptions(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    exc: Exception | None,
    status: HTTPStatus,
    error_msg: str,
) -> None:
    """Test sending message via notify.send_message action with exceptions."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://mobile-push.home-assistant.dev/push",
        json={
            "message": "Unknown error",
            "rateLimits": {
                "attempts": 1,
                "successful": 1,
                "errors": 0,
                "total": 1,
                "maximum": 150,
                "remaining": 149,
                "resetsAt": "1970-01-02T00:00:00Z",
            },
        },
        status=status,
        exc=exc,
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.test",
                ATTR_MESSAGE: "Hello world",
                ATTR_TITLE: "test",
            },
            blocking=True,
        )
    assert err.value.translation_key == error_msg
    assert err.value.translation_placeholders == {
        "device_name": "mobile_app test entry"
    }


@pytest.mark.usefixtures("setup_websocket_channel_only_push")
async def test_send_message_local_push_exception(hass: HomeAssistant) -> None:
    """Test send_message via local push with exceptions."""
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.websocket_push_name",
                ATTR_MESSAGE: "Hello world",
                ATTR_TITLE: "test",
            },
            blocking=True,
        )
    assert (
        err.value.translation_key == "device_not_connected_for_local_push_notifications"
    )
    assert err.value.translation_placeholders == {
        "device_name": "websocket push test entry"
    }


async def test_notify_live_activity_uses_stored_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_apple_push_receiver
) -> None:
    """Test that live_update notifications include live_activity_token in the relay payload."""
    # Simulate the iOS app having registered a per-activity token via webhook.
    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]["mock-webhook_id"] = {
        "washer_cycle": {
            "token": "LIVE_ACTIVITY_TOKEN_HEX",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }

    await hass.services.async_call(
        "notify",
        "mobile_app_apple_test_device",
        {
            "message": "45 minutes remaining",
            "target": ["mock-webhook_id"],
            "data": {"live_update": True, "tag": "washer_cycle", "progress": 2700},
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call_json = aioclient_mock.mock_calls[0][2]
    # A stored per-tag token means the activity is already running, so
    # it should be used together with the event update
    assert call_json == {
        "push_token": "PUSH_TOKEN",
        "live_activity_token": "LIVE_ACTIVITY_TOKEN_HEX",
        "message": "45 minutes remaining",
        "data": {
            "live_update": True,
            "tag": "washer_cycle",
            "progress": 2700,
            "event": "update",
        },
        "registration_info": {
            "app_id": "io.homeassistant.mobile_app",
            "app_version": "1.0",
            "os_version": "5.0.6",
            "webhook_id": "mock-webhook_id",
        },
    }


async def test_notify_live_activity_start(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
) -> None:
    """Test starting a new Live Activity with the push-to-start token.

    When there is no stored per-tag token yet, a ``live_update`` notification
    starts a fresh activity using the device's push-to-start token.
    """
    push_url = "https://mobile-push.home-assistant.dev/push"
    now = dt_util.naive_now() + timedelta(hours=24)
    iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    aioclient_mock.post(
        push_url,
        json={
            "rateLimits": {
                "successful": 1,
                "errors": 0,
                "maximum": 150,
                "resetsAt": iso_time,
            }
        },
    )

    entry = MockConfigEntry(
        data={
            "app_data": {
                "push_token": "FCM_TOKEN",
                "push_url": push_url,
                "start_live_activity_token": "PUSH_TO_START_HEX_TOKEN",
            },
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2024.1",
            "device_id": "ios-device-1",
            "device_name": "iPhone",
            "manufacturer": "Apple",
            "model": "iPhone 15",
            "os_name": "iOS",
            "os_version": "17.2",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "ios-webhook-1",
        },
        domain=DOMAIN,
        source="registration",
        title="iPhone entry",
        version=1,
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Laundry started",
            "target": ["ios-webhook-1"],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call_json = aioclient_mock.mock_calls[0][2]
    # No stored per-tag token → starting a fresh activity remotely with the
    # device's push-to-start token, so event=start.
    assert call_json == {
        "push_token": "FCM_TOKEN",
        "live_activity_token": "PUSH_TO_START_HEX_TOKEN",
        "message": "Laundry started",
        "data": {"live_update": True, "tag": "laundry", "event": "start"},
        "registration_info": {
            "app_id": "io.robbie.HomeAssistant",
            "app_version": "2024.1",
            "os_version": "17.2",
            "webhook_id": "ios-webhook-1",
        },
    }


async def test_notify_live_activity_without_tag_uses_fcm(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_apple_push_receiver
) -> None:
    """Test that live_update without a tag falls through to normal FCM push."""
    await hass.services.async_call(
        "notify",
        "mobile_app_apple_test_device",
        {
            "message": "No tag here",
            "target": ["mock-webhook_id"],
            "data": {"live_update": True},
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call_json = aioclient_mock.mock_calls[0][2]
    # Should use normal FCM token since there is no tag.
    assert call_json == {
        "push_token": "PUSH_TOKEN",
        "message": "No tag here",
        "data": {"live_update": True},
        "registration_info": {
            "app_id": "io.homeassistant.mobile_app",
            "app_version": "1.0",
            "os_version": "5.0.6",
            "webhook_id": "mock-webhook_id",
        },
    }


async def test_notify_normal_notification_ignores_live_activity_tokens(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_apple_push_receiver
) -> None:
    """Test that normal notifications don't route through live activity tokens."""
    # Store a live activity token — it should be ignored for non-live-activity pushes.
    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]["mock-webhook_id"] = {
        "some_tag": {
            "token": "SHOULD_NOT_USE_THIS",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }

    await hass.services.async_call(
        "notify",
        "mobile_app_apple_test_device",
        {
            "message": "Normal notification",
            "target": ["mock-webhook_id"],
            "data": {"tag": "some_tag"},
        },
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call_json = aioclient_mock.mock_calls[0][2]
    # Should use normal FCM token — live_update flag not set.
    assert call_json == {
        "push_token": "PUSH_TOKEN",
        "message": "Normal notification",
        "data": {"tag": "some_tag"},
        "registration_info": {
            "app_id": "io.homeassistant.mobile_app",
            "app_version": "1.0",
            "os_version": "5.0.6",
            "webhook_id": "mock-webhook_id",
        },
    }


async def test_notify_clear_notification_allows_same_tag_to_start_again(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
) -> None:
    """Test clear_notification removes the tag token so recurring automations restart."""
    push_url = "https://mobile-push.home-assistant.dev/push"
    now = dt_util.naive_now() + timedelta(hours=24)
    iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    aioclient_mock.post(
        push_url,
        json={
            "rateLimits": {
                "successful": 1,
                "errors": 0,
                "maximum": 150,
                "resetsAt": iso_time,
            }
        },
    )

    entry = MockConfigEntry(
        data={
            "app_data": {
                "push_token": "FCM_TOKEN",
                "push_url": push_url,
                "start_live_activity_token": "PUSH_TO_START_HEX_TOKEN",
            },
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2024.1",
            "device_id": "ios-device-1",
            "device_name": "iPhone",
            "manufacturer": "Apple",
            "model": "iPhone 15",
            "os_name": "iOS",
            "os_version": "17.2",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "ios-webhook-1",
        },
        domain=DOMAIN,
        source="registration",
        title="iPhone entry",
        version=1,
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]["ios-webhook-1"] = {
        "laundry": {
            "token": "TOKEN_TO_END",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "clear_notification",
            "target": ["ios-webhook-1"],
            "data": {"tag": "laundry"},
        },
        blocking=True,
    )
    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Laundry started",
            "target": ["ios-webhook-1"],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )

    assert aioclient_mock.mock_calls[0][2] == {
        "push_token": "FCM_TOKEN",
        "live_activity_token": "TOKEN_TO_END",
        "message": "clear_notification",
        "data": {"tag": "laundry", "event": "end"},
        "registration_info": {
            "app_id": "io.robbie.HomeAssistant",
            "app_version": "2024.1",
            "os_version": "17.2",
            "webhook_id": "ios-webhook-1",
        },
    }
    assert aioclient_mock.mock_calls[1][2] == {
        "push_token": "FCM_TOKEN",
        "live_activity_token": "PUSH_TO_START_HEX_TOKEN",
        "message": "Laundry started",
        "data": {"live_update": True, "tag": "laundry", "event": "start"},
        "registration_info": {
            "app_id": "io.robbie.HomeAssistant",
            "app_version": "2024.1",
            "os_version": "17.2",
            "webhook_id": "ios-webhook-1",
        },
    }


async def test_notify_clear_notification_without_stored_token_passes_through(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_apple_push_receiver
) -> None:
    """Test clear_notification with no matching live activity is unmodified."""
    await hass.services.async_call(
        "notify",
        "mobile_app_apple_test_device",
        {
            "message": "clear_notification",
            "target": ["mock-webhook_id"],
            "data": {"tag": "no_such_activity"},
        },
        blocking=True,
    )

    assert aioclient_mock.mock_calls[0][2] == {
        "push_token": "PUSH_TOKEN",
        "message": "clear_notification",
        "data": {"tag": "no_such_activity"},
        "registration_info": {
            "app_id": "io.homeassistant.mobile_app",
            "app_version": "1.0",
            "os_version": "5.0.6",
            "webhook_id": "mock-webhook_id",
        },
    }


async def test_notify_clear_notification_without_tag_passes_through(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, setup_apple_push_receiver
) -> None:
    """Test clear_notification without a tag never enters the live activity path."""
    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]["mock-webhook_id"] = {
        "washer_cycle": {
            "token": "TOKEN",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }

    await hass.services.async_call(
        "notify",
        "mobile_app_apple_test_device",
        {
            "message": "clear_notification",
            "target": ["mock-webhook_id"],
        },
        blocking=True,
    )

    assert aioclient_mock.mock_calls[0][2] == {
        "push_token": "PUSH_TOKEN",
        "message": "clear_notification",
        "registration_info": {
            "app_id": "io.homeassistant.mobile_app",
            "app_version": "1.0",
            "os_version": "5.0.6",
            "webhook_id": "mock-webhook_id",
        },
    }


async def test_notify_non_apple_device_skips_live_activity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
) -> None:
    """Test that a non-Apple device never enters the Live Activity code path."""
    push_url = "https://mobile-push.home-assistant.dev/push"
    now = dt_util.naive_now() + timedelta(hours=24)
    iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    aioclient_mock.post(
        push_url,
        json={
            "rateLimits": {
                "successful": 1,
                "errors": 0,
                "maximum": 150,
                "resetsAt": iso_time,
            }
        },
    )

    entry = MockConfigEntry(
        data={
            "app_data": {
                "push_token": "FCM_TOKEN",
                "push_url": push_url,
            },
            "app_id": "io.homeassistant.companion.android",
            "app_name": "Home Assistant",
            "app_version": "2024.1",
            "device_id": "android-device-1",
            "device_name": "Pixel",
            "manufacturer": "Google",
            "model": "Pixel 8",
            "os_name": "Android",
            "os_version": "14",
            "supports_encryption": False,
            "user_id": hass_admin_user.id,
            "webhook_id": "android-webhook-1",
        },
        domain=DOMAIN,
        source="registration",
        title="Pixel entry",
        version=1,
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    # A stored token would be resolved on an Apple device, but must be ignored here.
    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]["android-webhook-1"] = {
        "laundry": {
            "token": "SHOULD_NOT_USE_THIS",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }

    with patch(
        "homeassistant.components.mobile_app.notify.prepare_live_activity_remote_push"
    ) as mock_prepare:
        await hass.services.async_call(
            "notify",
            "mobile_app_pixel",
            {
                "message": "Laundry started",
                "target": ["android-webhook-1"],
                "data": {"live_update": True, "tag": "laundry"},
            },
            blocking=True,
        )

    mock_prepare.assert_not_called()
    assert aioclient_mock.mock_calls[0][2] == {
        "push_token": "FCM_TOKEN",
        "message": "Laundry started",
        "data": {"live_update": True, "tag": "laundry"},
        "registration_info": {
            "app_id": "io.homeassistant.companion.android",
            "app_version": "2024.1",
            "os_version": "14",
            "webhook_id": "android-webhook-1",
        },
    }


async def _setup_iphone_with_push_to_start(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    admin_user: MockUser,
) -> str:
    """Register an Apple device with a push-to-start token and a mocked relay."""
    push_url = "https://mobile-push.home-assistant.dev/push"
    now = dt_util.naive_now() + timedelta(hours=24)
    iso_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    aioclient_mock.post(
        push_url,
        json={
            "rateLimits": {
                "successful": 1,
                "errors": 0,
                "maximum": 150,
                "resetsAt": iso_time,
            }
        },
    )

    webhook_id = "ios-webhook-1"
    entry = MockConfigEntry(
        data={
            "app_data": {
                "push_token": "FCM_TOKEN",
                "push_url": push_url,
                "start_live_activity_token": "PUSH_TO_START_HEX_TOKEN",
            },
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2024.1",
            "device_id": "ios-device-1",
            "device_name": "iPhone",
            "manufacturer": "Apple",
            "model": "iPhone 15",
            "os_name": "iOS",
            "os_version": "17.2",
            "supports_encryption": False,
            "user_id": admin_user.id,
            "webhook_id": webhook_id,
        },
        domain=DOMAIN,
        source="registration",
        title="iPhone entry",
        version=1,
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return webhook_id


async def test_notify_live_activity_start_suppressed_within_cooldown(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A second START for the same tag inside the cooldown window is suppressed."""
    webhook_id = await _setup_iphone_with_push_to_start(
        hass, aioclient_mock, hass_admin_user
    )

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Laundry started",
            "target": [webhook_id],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 1
    assert webhook_id in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS]
    assert "laundry" in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS][webhook_id]

    with caplog.at_level(logging.WARNING):
        await hass.services.async_call(
            "notify",
            "mobile_app_iphone",
            {
                "message": "Laundry still going",
                "target": [webhook_id],
                "data": {"live_update": True, "tag": "laundry"},
            },
            blocking=True,
        )

    assert len(aioclient_mock.mock_calls) == 1
    assert any(
        "Live Activity start for tag 'laundry' was sent recently" in record.message
        for record in caplog.records
    )


async def test_notify_live_activity_start_allowed_after_cooldown_expires(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Once the cooldown window passes, a fresh START for the same tag goes through."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    webhook_id = await _setup_iphone_with_push_to_start(
        hass, aioclient_mock, hass_admin_user
    )

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "First start",
            "target": [webhook_id],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 1

    freezer.tick(timedelta(seconds=LIVE_ACTIVITY_START_COOLDOWN_SECONDS + 1))

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Fresh start",
            "target": [webhook_id],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 2


async def test_notify_live_activity_token_clears_pending_start(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
) -> None:
    """Reporting the per-activity token clears the pending start so updates can flow."""
    webhook_id = await _setup_iphone_with_push_to_start(
        hass, aioclient_mock, hass_admin_user
    )

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Laundry started",
            "target": [webhook_id],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )
    assert "laundry" in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS][webhook_id]

    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS][webhook_id] = {
        "laundry": {
            "token": "PER_ACTIVITY_TOKEN",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }
    clear_start_pending(hass, webhook_id, "laundry")
    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS] == {}

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Laundry 50%",
            "target": [webhook_id],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 2
    second_call = aioclient_mock.mock_calls[1][2]
    assert second_call["data"]["event"] == "update"
    assert second_call["live_activity_token"] == "PER_ACTIVITY_TOKEN"


async def test_notify_live_activity_clear_notification_releases_pending(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_admin_user: MockUser,
) -> None:
    """Sending clear_notification with a stored token releases any pending start."""
    webhook_id = await _setup_iphone_with_push_to_start(
        hass, aioclient_mock, hass_admin_user
    )

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "Laundry started",
            "target": [webhook_id],
            "data": {"live_update": True, "tag": "laundry"},
        },
        blocking=True,
    )
    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS] != {}

    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS][webhook_id] = {
        "laundry": {
            "token": "PER_ACTIVITY_TOKEN",
            "expires_at": dt_util.utcnow().timestamp() + 3600,
        }
    }

    await hass.services.async_call(
        "notify",
        "mobile_app_iphone",
        {
            "message": "clear_notification",
            "target": [webhook_id],
            "data": {"tag": "laundry"},
        },
        blocking=True,
    )

    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_PENDING_STARTS] == {}
