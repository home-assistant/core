"""Test HTML5 notify platform."""

from http import HTTPStatus
import json
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

from aiohttp import ClientError
from aiohttp.hdrs import AUTHORIZATION
import pytest
from pywebpush import WebPushException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.html5 import notify as html5
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator

CONFIG_FILE = "file.conf"

VAPID_CONF = {
    "platform": "html5",
    "vapid_pub_key": (
        "BJMA2gDZEkHaXRhf1fhY_"
        "QbKbhVIHlSJXI0bFyo0eJXnUPOjdgycCAbj-2bMKMKNKs"
        "_rM8JoSnyKGCXAY2dbONI"
    ),
    "vapid_prv_key": "ZwPgwKpESGuGLMZYU39vKgrekrWzCijo-LsBM3CZ9-c",
    "vapid_email": "someone@example.com",
}

SUBSCRIPTION_1 = {
    "browser": "chrome",
    "subscription": {
        "endpoint": "https://googleapis.com",
        "keys": {"auth": "auth", "p256dh": "p256dh"},
    },
}
SUBSCRIPTION_2 = {
    "browser": "firefox",
    "subscription": {
        "endpoint": "https://example.com",
        "keys": {"auth": "bla", "p256dh": "bla"},
    },
}
SUBSCRIPTION_3 = {
    "browser": "chrome",
    "subscription": {
        "endpoint": "https://example.com/not_exist",
        "keys": {"auth": "bla", "p256dh": "bla"},
    },
}
SUBSCRIPTION_4 = {
    "browser": "chrome",
    "subscription": {
        "endpoint": "https://googleapis.com",
        "expirationTime": None,
        "keys": {"auth": "auth", "p256dh": "p256dh"},
    },
}

SUBSCRIPTION_5 = {
    "browser": "chrome",
    "subscription": {
        "endpoint": "https://fcm.googleapis.com/fcm/send/LONG-RANDOM-KEY",
        "expirationTime": None,
        "keys": {"auth": "auth", "p256dh": "p256dh"},
    },
}

REGISTER_URL = "/api/notify.html5"
PUBLISH_URL = "/api/notify.html5/callback"

VAPID_HEADERS = {
    "Authorization": "vapid t=signed!!!",
    "urgency": "normal",
    "priority": "normal",
}


async def test_get_service_with_no_json(hass: HomeAssistant) -> None:
    """Test empty json file."""
    await async_setup_component(hass, "http", {})
    m = mock_open()
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)

    assert service is not None


@pytest.mark.usefixtures("mock_jwt", "mock_vapid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_dismissing_message(mock_wp: AsyncMock, hass: HomeAssistant) -> None:
    """Test dismissing message."""
    await async_setup_component(hass, "http", {})

    data = {"device": SUBSCRIPTION_1}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_dismiss(target=["device", "non_existing"], data={"tag": "test"})

    mock_wp.send_async.assert_awaited_once_with(
        data='{"tag": "test", "dismiss": true, "data": {"jwt": "JWT"}, "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_sending_message(mock_wp: AsyncMock, hass: HomeAssistant) -> None:
    """Test sending message."""
    await async_setup_component(hass, "http", {})

    data = {"device": SUBSCRIPTION_1}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message(
        "Hello", target=["device", "non_existing"], data={"icon": "beer.png"}
    )

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"url": "/", "jwt": "JWT"}, "icon": "beer.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )

    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_1["subscription"]


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_fcm_key_include(mock_wp: AsyncMock, hass: HomeAssistant) -> None:
    """Test if the FCM header is included."""
    await async_setup_component(hass, "http", {})

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello", target=["chrome"])

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"url": "/", "jwt": "JWT"}, "icon": "/static/icons/favicon-192x192.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )

    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_5["subscription"]


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_fcm_send_with_unknown_priority(
    mock_wp: AsyncMock, hass: HomeAssistant
) -> None:
    """Test if the gcm_key is only included for GCM endpoints."""
    await async_setup_component(hass, "http", {})

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello", target=["chrome"], priority="undefined")

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"url": "/", "jwt": "JWT"}, "icon": "/static/icons/favicon-192x192.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )
    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_5["subscription"]


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_fcm_no_targets(mock_wp: AsyncMock, hass: HomeAssistant) -> None:
    """Test if the gcm_key is only included for GCM endpoints."""
    await async_setup_component(hass, "http", {})

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello")

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"url": "/", "jwt": "JWT"}, "icon": "/static/icons/favicon-192x192.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )
    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_5["subscription"]


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_fcm_additional_data(mock_wp: AsyncMock, hass: HomeAssistant) -> None:
    """Test if the gcm_key is only included for GCM endpoints."""
    await async_setup_component(hass, "http", {})

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello", data={"mykey": "myvalue"})

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"mykey": "myvalue", "url": "/", "jwt": "JWT"}, "icon": "/static/icons/favicon-192x192.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )
    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_5["subscription"]


@pytest.mark.usefixtures("load_config")
async def test_registering_new_device_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the HTML view works."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_1))

    assert resp.status == HTTPStatus.OK
    assert len(mock_save.mock_calls) == 1
    assert mock_save.mock_calls[0][1][1] == {"unnamed device": SUBSCRIPTION_1}


@pytest.mark.usefixtures("load_config")
async def test_registering_new_device_view_with_name(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the HTML view works with name attribute."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    SUB_WITH_NAME = SUBSCRIPTION_1.copy()
    SUB_WITH_NAME["name"] = "test device"

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.post(REGISTER_URL, data=json.dumps(SUB_WITH_NAME))

    assert resp.status == HTTPStatus.OK
    assert len(mock_save.mock_calls) == 1
    assert mock_save.mock_calls[0][1][1] == {"test device": SUBSCRIPTION_1}


@pytest.mark.usefixtures("load_config")
async def test_registering_new_device_expiration_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the HTML view works."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.OK
    assert mock_save.mock_calls[0][1][1] == {"unnamed device": SUBSCRIPTION_4}


@pytest.mark.usefixtures("load_config")
async def test_registering_new_device_fails_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test subs. are not altered when registering a new device fails."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()
    with patch(
        "homeassistant.components.html5.notify.save_json",
        side_effect=HomeAssistantError(),
    ):
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.usefixtures("load_config")
async def test_registering_existing_device_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test subscription is updated when registering existing device."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_1))
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.OK
    mock_save.assert_called_with(
        hass.config.path(html5.REGISTRATIONS_FILE), {"unnamed device": SUBSCRIPTION_4}
    )


@pytest.mark.usefixtures("load_config")
async def test_registering_existing_device_view_with_name(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test subscription is updated when reg'ing existing device with name."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    SUB_WITH_NAME = SUBSCRIPTION_1.copy()
    SUB_WITH_NAME["name"] = "test device"

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        await client.post(REGISTER_URL, data=json.dumps(SUB_WITH_NAME))
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.OK

    mock_save.assert_called_with(
        hass.config.path(html5.REGISTRATIONS_FILE), {"test device": SUBSCRIPTION_4}
    )


@pytest.mark.usefixtures("load_config")
async def test_registering_existing_device_fails_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test sub. is not updated when registering existing device fails."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_1))
        mock_save.side_effect = HomeAssistantError
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.usefixtures("load_config")
async def test_registering_new_device_validation(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test various errors when registering a new device."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    resp = await client.post(
        REGISTER_URL,
        data=json.dumps({"browser": "invalid browser", "subscription": "sub info"}),
    )
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post(REGISTER_URL, data=json.dumps({"browser": "chrome"}))
    assert resp.status == HTTPStatus.BAD_REQUEST

    with patch("homeassistant.components.html5.notify.save_json", return_value=False):
        resp = await client.post(
            REGISTER_URL,
            data=json.dumps({"browser": "chrome", "subscription": "sub info"}),
        )
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_unregistering_device_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
) -> None:
    """Test that the HTML unregister view works."""
    load_config.return_value = {
        "some device": SUBSCRIPTION_1,
        "other device": SUBSCRIPTION_2,
    }
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.delete(
            REGISTER_URL,
            data=json.dumps({"subscription": SUBSCRIPTION_1["subscription"]}),
        )

    assert resp.status == HTTPStatus.OK
    assert len(mock_save.mock_calls) == 1
    mock_save.assert_called_once_with(
        hass.config.path(html5.REGISTRATIONS_FILE), {"other device": SUBSCRIPTION_2}
    )


@pytest.mark.usefixtures("load_config")
async def test_unregister_device_view_handle_unknown_subscription(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the HTML unregister view handles unknown subscriptions."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.delete(
            REGISTER_URL,
            data=json.dumps({"subscription": SUBSCRIPTION_3["subscription"]}),
        )

    assert resp.status == HTTPStatus.OK, resp.response
    assert len(mock_save.mock_calls) == 0


async def test_unregistering_device_view_handles_save_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
) -> None:
    """Test that the HTML unregister view handles save errors."""
    load_config.return_value = {
        "some device": SUBSCRIPTION_1,
        "other device": SUBSCRIPTION_2,
    }
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    with patch(
        "homeassistant.components.html5.notify.save_json",
        side_effect=HomeAssistantError(),
    ):
        resp = await client.delete(
            REGISTER_URL,
            data=json.dumps({"subscription": SUBSCRIPTION_1["subscription"]}),
        )

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR, resp.response


@pytest.mark.usefixtures("load_config")
async def test_callback_view_no_jwt(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the notification callback view works without JWT."""
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()
    resp = await client.post(
        PUBLISH_URL,
        data=json.dumps(
            {"type": "push", "tag": "3bc28d69-0921-41f1-ac6a-7a627ba0aa72"}
        ),
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_callback_view_with_jwt(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    mock_wp: AsyncMock,
) -> None:
    """Test that the notification callback view works with JWT."""
    load_config.return_value = {"device": SUBSCRIPTION_1}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_client()

    await hass.services.async_call(
        "notify",
        "html5",
        {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
        blocking=True,
    )

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"url": "/", "jwt": "JWT"}, "icon": "beer.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )
    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_1["subscription"]

    bearer_token = "Bearer JWT"

    resp = await client.post(
        PUBLISH_URL, json={"type": "push"}, headers={AUTHORIZATION: bearer_token}
    )

    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert body == {"event": "push", "status": "ok"}


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_fcm_without_targets(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    mock_wp: AsyncMock,
) -> None:
    """Test that the notification is send with FCM without targets."""
    load_config.return_value = {"device": SUBSCRIPTION_5}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "notify",
        "html5",
        {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
        blocking=True,
    )

    mock_wp.send_async.assert_awaited_once_with(
        data='{"badge": "/static/images/notification-badge.png", "body": "Hello", "data": {"url": "/", "jwt": "JWT"}, "icon": "beer.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Home Assistant", "timestamp": 1234567890000}',
        headers=VAPID_HEADERS,
        ttl=86400,
    )
    # WebPusher constructor
    assert mock_wp.cls.call_args[0][0] == SUBSCRIPTION_5["subscription"]


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_fcm_expired(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    mock_wp: AsyncMock,
) -> None:
    """Test that the FCM target is removed when expired."""
    load_config.return_value = {"device": SUBSCRIPTION_5}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_wp.send_async.return_value.status = 410
    with (
        patch("homeassistant.components.html5.notify.save_json") as mock_save,
    ):
        await hass.services.async_call(
            "notify",
            "html5",
            {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
            blocking=True,
        )
    # "device" should be removed when expired.
    mock_save.assert_called_once_with(hass.config.path(html5.REGISTRATIONS_FILE), {})


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_fcm_expired_save_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    load_config: MagicMock,
    caplog: pytest.LogCaptureFixture,
    mock_wp: AsyncMock,
) -> None:
    """Test that the FCM target remains after expiry if save_json fails."""
    load_config.return_value = {"device": SUBSCRIPTION_5}
    await async_setup_component(hass, "http", {})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_wp.send_async.return_value.status = 410
    with (
        patch(
            "homeassistant.components.html5.notify.save_json",
            side_effect=HomeAssistantError(),
        ),
    ):
        await hass.services.async_call(
            "notify",
            "html5",
            {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
            blocking=True,
        )
    # "device" should still exist if save fails.
    assert "Error saving registration" in caplog.text


async def test_notify_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    load_config: MagicMock,
) -> None:
    """Test setup of the notify platform."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webpush_async: AsyncMock,
    load_config: MagicMock,
) -> None:
    """Test sending a message."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.my_desktop")
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.my_desktop",
            ATTR_MESSAGE: "World",
            ATTR_TITLE: "Hello",
        },
        blocking=True,
    )

    state = hass.states.get("notify.my_desktop")
    assert state
    assert state.state == "2009-02-13T23:31:30+00:00"

    webpush_async.assert_awaited_once()
    assert webpush_async.await_args
    assert webpush_async.await_args.args == (
        {
            "endpoint": "https://googleapis.com",
            "keys": {"auth": "auth", "p256dh": "p256dh"},
        },
        '{"badge": "/static/images/notification-badge.png", "body": "World", "icon": "/static/icons/favicon-192x192.png", "tag": "12345678-1234-5678-1234-567812345678", "title": "Hello", "timestamp": 1234567890000, "data": {"jwt": "JWT"}}',
        "h6acSRds8_KR8hT9djD8WucTL06Gfe29XXyZ1KcUjN8",
        {
            "sub": "mailto:test@example.com",
            "aud": "https://googleapis.com",
            "exp": 1234611090,
        },
    )


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (
            WebPushException("", response=Mock(status=HTTPStatus.IM_A_TEAPOT)),
            "request_error",
        ),
        (
            WebPushException("", response=Mock(status=HTTPStatus.GONE)),
            "channel_expired",
        ),
        (
            ClientError,
            "connection_error",
        ),
    ],
)
@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_message_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webpush_async: AsyncMock,
    load_config: MagicMock,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test sending a message with exceptions."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    webpush_async.side_effect = exception

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.my_desktop",
                ATTR_MESSAGE: "World",
                ATTR_TITLE: "Hello",
            },
            blocking=True,
        )
    assert e.value.translation_key == translation_key


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_message_save_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webpush_async: AsyncMock,
    load_config: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending a message with channel expired but saving registration fails."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    webpush_async.side_effect = (
        WebPushException("", response=Mock(status=HTTPStatus.GONE)),
    )
    with (
        patch(
            "homeassistant.components.html5.notify.save_json",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(HomeAssistantError) as e,
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.my_desktop",
                ATTR_MESSAGE: "World",
                ATTR_TITLE: "Hello",
            },
            blocking=True,
        )
    assert e.value.translation_key == "channel_expired"

    assert "Error saving registration" in caplog.text


@pytest.mark.usefixtures("mock_jwt", "mock_vapid", "mock_uuid")
@pytest.mark.freeze_time("2009-02-13T23:31:30.000Z")
async def test_send_message_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    webpush_async: AsyncMock,
    load_config: MagicMock,
) -> None:
    """Test sending a message with channel expired and entity goes unavailable."""
    load_config.return_value = {"my-desktop": SUBSCRIPTION_1}

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    webpush_async.side_effect = (
        WebPushException("", response=Mock(status=HTTPStatus.GONE)),
    )
    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.my_desktop",
                ATTR_MESSAGE: "World",
                ATTR_TITLE: "Hello",
            },
            blocking=True,
        )
    assert e.value.translation_key == "channel_expired"

    state = hass.states.get("notify.my_desktop")
    assert state
    assert state.state == STATE_UNAVAILABLE
