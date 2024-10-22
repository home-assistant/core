"""Test HTML5 notify platform."""

from http import HTTPStatus
import json
from typing import Any
from unittest.mock import mock_open, patch

from aiohttp.hdrs import AUTHORIZATION
from aiohttp.test_utils import TestClient

import homeassistant.components.html5.notify as html5
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

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


async def mock_client(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    registrations: dict[str, Any] | None = None,
) -> TestClient:
    """Create a test client for HTML5 views."""
    if registrations is None:
        registrations = {}

    with patch(
        "homeassistant.components.html5.notify._load_config", return_value=registrations
    ):
        await async_setup_component(hass, "notify", {"notify": VAPID_CONF})
        await hass.async_block_till_done()

    return await hass_client()


async def test_get_service_with_no_json(hass: HomeAssistant) -> None:
    """Test empty json file."""
    await async_setup_component(hass, "http", {})
    m = mock_open()
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)

    assert service is not None


@patch("homeassistant.components.html5.notify.WebPusher")
async def test_dismissing_message(mock_wp, hass: HomeAssistant) -> None:
    """Test dismissing message."""
    await async_setup_component(hass, "http", {})
    mock_wp().send().status_code = 201

    data = {"device": SUBSCRIPTION_1}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_dismiss(target=["device", "non_existing"], data={"tag": "test"})

    assert len(mock_wp.mock_calls) == 4

    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_1["subscription"]

    # Call to send
    payload = json.loads(mock_wp.mock_calls[3][2]["data"])

    assert payload["dismiss"] is True
    assert payload["tag"] == "test"


@patch("homeassistant.components.html5.notify.WebPusher")
async def test_sending_message(mock_wp, hass: HomeAssistant) -> None:
    """Test sending message."""
    await async_setup_component(hass, "http", {})
    mock_wp().send().status_code = 201

    data = {"device": SUBSCRIPTION_1}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message(
        "Hello", target=["device", "non_existing"], data={"icon": "beer.png"}
    )

    assert len(mock_wp.mock_calls) == 4

    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_1["subscription"]

    # Call to send
    payload = json.loads(mock_wp.mock_calls[3][2]["data"])

    assert payload["body"] == "Hello"
    assert payload["icon"] == "beer.png"


@patch("homeassistant.components.html5.notify.WebPusher")
async def test_fcm_key_include(mock_wp, hass: HomeAssistant) -> None:
    """Test if the FCM header is included."""
    await async_setup_component(hass, "http", {})
    mock_wp().send().status_code = 201

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello", target=["chrome"])

    assert len(mock_wp.mock_calls) == 4
    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_5["subscription"]

    # Get the keys passed to the WebPusher's send method
    assert mock_wp.mock_calls[3][2]["headers"]["Authorization"] is not None


@patch("homeassistant.components.html5.notify.WebPusher")
async def test_fcm_send_with_unknown_priority(mock_wp, hass: HomeAssistant) -> None:
    """Test if the gcm_key is only included for GCM endpoints."""
    await async_setup_component(hass, "http", {})
    mock_wp().send().status_code = 201

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello", target=["chrome"], priority="undefined")

    assert len(mock_wp.mock_calls) == 4
    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_5["subscription"]

    # Get the keys passed to the WebPusher's send method
    assert mock_wp.mock_calls[3][2]["headers"]["priority"] == "normal"


@patch("homeassistant.components.html5.notify.WebPusher")
async def test_fcm_no_targets(mock_wp, hass: HomeAssistant) -> None:
    """Test if the gcm_key is only included for GCM endpoints."""
    await async_setup_component(hass, "http", {})
    mock_wp().send().status_code = 201

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello")

    assert len(mock_wp.mock_calls) == 4
    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_5["subscription"]

    # Get the keys passed to the WebPusher's send method
    assert mock_wp.mock_calls[3][2]["headers"]["priority"] == "normal"


@patch("homeassistant.components.html5.notify.WebPusher")
async def test_fcm_additional_data(mock_wp, hass: HomeAssistant) -> None:
    """Test if the gcm_key is only included for GCM endpoints."""
    await async_setup_component(hass, "http", {})
    mock_wp().send().status_code = 201

    data = {"chrome": SUBSCRIPTION_5}

    m = mock_open(read_data=json.dumps(data))
    with patch("homeassistant.util.json.open", m, create=True):
        service = await html5.async_get_service(hass, {}, VAPID_CONF)
        service.hass = hass

    assert service is not None

    await service.async_send_message("Hello", data={"mykey": "myvalue"})

    assert len(mock_wp.mock_calls) == 4
    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_5["subscription"]

    # Get the keys passed to the WebPusher's send method
    assert mock_wp.mock_calls[3][2]["headers"]["priority"] == "normal"


async def test_registering_new_device_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the HTML view works."""
    client = await mock_client(hass, hass_client)

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_1))

    assert resp.status == HTTPStatus.OK
    assert len(mock_save.mock_calls) == 1
    assert mock_save.mock_calls[0][1][1] == {"unnamed device": SUBSCRIPTION_1}


async def test_registering_new_device_view_with_name(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the HTML view works with name attribute."""
    client = await mock_client(hass, hass_client)

    SUB_WITH_NAME = SUBSCRIPTION_1.copy()
    SUB_WITH_NAME["name"] = "test device"

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.post(REGISTER_URL, data=json.dumps(SUB_WITH_NAME))

    assert resp.status == HTTPStatus.OK
    assert len(mock_save.mock_calls) == 1
    assert mock_save.mock_calls[0][1][1] == {"test device": SUBSCRIPTION_1}


async def test_registering_new_device_expiration_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the HTML view works."""
    client = await mock_client(hass, hass_client)

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.OK
    assert mock_save.mock_calls[0][1][1] == {"unnamed device": SUBSCRIPTION_4}


async def test_registering_new_device_fails_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test subs. are not altered when registering a new device fails."""
    registrations = {}
    client = await mock_client(hass, hass_client, registrations)

    with patch(
        "homeassistant.components.html5.notify.save_json",
        side_effect=HomeAssistantError(),
    ):
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert registrations == {}


async def test_registering_existing_device_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test subscription is updated when registering existing device."""
    registrations = {}
    client = await mock_client(hass, hass_client, registrations)

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_1))
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.OK
    assert mock_save.mock_calls[0][1][1] == {"unnamed device": SUBSCRIPTION_4}
    assert registrations == {"unnamed device": SUBSCRIPTION_4}


async def test_registering_existing_device_view_with_name(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test subscription is updated when reg'ing existing device with name."""
    registrations = {}
    client = await mock_client(hass, hass_client, registrations)

    SUB_WITH_NAME = SUBSCRIPTION_1.copy()
    SUB_WITH_NAME["name"] = "test device"

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        await client.post(REGISTER_URL, data=json.dumps(SUB_WITH_NAME))
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.OK
    assert mock_save.mock_calls[0][1][1] == {"test device": SUBSCRIPTION_4}
    assert registrations == {"test device": SUBSCRIPTION_4}


async def test_registering_existing_device_fails_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test sub. is not updated when registering existing device fails."""
    registrations = {}
    client = await mock_client(hass, hass_client, registrations)

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_1))
        mock_save.side_effect = HomeAssistantError
        resp = await client.post(REGISTER_URL, data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert registrations == {"unnamed device": SUBSCRIPTION_1}


async def test_registering_new_device_validation(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test various errors when registering a new device."""
    client = await mock_client(hass, hass_client)

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
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the HTML unregister view works."""
    registrations = {"some device": SUBSCRIPTION_1, "other device": SUBSCRIPTION_2}
    client = await mock_client(hass, hass_client, registrations)

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.delete(
            REGISTER_URL,
            data=json.dumps({"subscription": SUBSCRIPTION_1["subscription"]}),
        )

    assert resp.status == HTTPStatus.OK
    assert len(mock_save.mock_calls) == 1
    assert registrations == {"other device": SUBSCRIPTION_2}


async def test_unregister_device_view_handle_unknown_subscription(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the HTML unregister view handles unknown subscriptions."""
    registrations = {}
    client = await mock_client(hass, hass_client, registrations)

    with patch("homeassistant.components.html5.notify.save_json") as mock_save:
        resp = await client.delete(
            REGISTER_URL,
            data=json.dumps({"subscription": SUBSCRIPTION_3["subscription"]}),
        )

    assert resp.status == HTTPStatus.OK, resp.response
    assert registrations == {}
    assert len(mock_save.mock_calls) == 0


async def test_unregistering_device_view_handles_save_error(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the HTML unregister view handles save errors."""
    registrations = {"some device": SUBSCRIPTION_1, "other device": SUBSCRIPTION_2}
    client = await mock_client(hass, hass_client, registrations)

    with patch(
        "homeassistant.components.html5.notify.save_json",
        side_effect=HomeAssistantError(),
    ):
        resp = await client.delete(
            REGISTER_URL,
            data=json.dumps({"subscription": SUBSCRIPTION_1["subscription"]}),
        )

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR, resp.response
    assert registrations == {
        "some device": SUBSCRIPTION_1,
        "other device": SUBSCRIPTION_2,
    }


async def test_callback_view_no_jwt(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the notification callback view works without JWT."""
    client = await mock_client(hass, hass_client)
    resp = await client.post(
        PUBLISH_URL,
        data=json.dumps(
            {"type": "push", "tag": "3bc28d69-0921-41f1-ac6a-7a627ba0aa72"}
        ),
    )

    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_callback_view_with_jwt(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the notification callback view works with JWT."""
    registrations = {"device": SUBSCRIPTION_1}
    client = await mock_client(hass, hass_client, registrations)

    with patch("homeassistant.components.html5.notify.WebPusher") as mock_wp:
        mock_wp().send().status_code = 201
        await hass.services.async_call(
            "notify",
            "html5",
            {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
            blocking=True,
        )

    assert len(mock_wp.mock_calls) == 4

    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_1["subscription"]

    # Call to send
    push_payload = json.loads(mock_wp.mock_calls[3][2]["data"])

    assert push_payload["body"] == "Hello"
    assert push_payload["icon"] == "beer.png"

    bearer_token = f"Bearer {push_payload['data']['jwt']}"

    resp = await client.post(
        PUBLISH_URL, json={"type": "push"}, headers={AUTHORIZATION: bearer_token}
    )

    assert resp.status == HTTPStatus.OK
    body = await resp.json()
    assert body == {"event": "push", "status": "ok"}


async def test_send_fcm_without_targets(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the notification is send with FCM without targets."""
    registrations = {"device": SUBSCRIPTION_5}
    await mock_client(hass, hass_client, registrations)
    with patch("homeassistant.components.html5.notify.WebPusher") as mock_wp:
        mock_wp().send().status_code = 201
        await hass.services.async_call(
            "notify",
            "html5",
            {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
            blocking=True,
        )

    assert len(mock_wp.mock_calls) == 4

    # WebPusher constructor
    assert mock_wp.mock_calls[2][1][0] == SUBSCRIPTION_5["subscription"]


async def test_send_fcm_expired(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the FCM target is removed when expired."""
    registrations = {"device": SUBSCRIPTION_5}
    await mock_client(hass, hass_client, registrations)

    with (
        patch("homeassistant.components.html5.notify.WebPusher") as mock_wp,
        patch("homeassistant.components.html5.notify.save_json"),
    ):
        mock_wp().send().status_code = 410
        await hass.services.async_call(
            "notify",
            "html5",
            {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
            blocking=True,
        )
    # "device" should be removed when expired.
    assert "device" not in registrations


async def test_send_fcm_expired_save_fails(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that the FCM target remains after expiry if save_json fails."""
    registrations = {"device": SUBSCRIPTION_5}
    await mock_client(hass, hass_client, registrations)

    with (
        patch("homeassistant.components.html5.notify.WebPusher") as mock_wp,
        patch(
            "homeassistant.components.html5.notify.save_json",
            side_effect=HomeAssistantError(),
        ),
    ):
        mock_wp().send().status_code = 410
        await hass.services.async_call(
            "notify",
            "html5",
            {"message": "Hello", "target": ["device"], "data": {"icon": "beer.png"}},
            blocking=True,
        )
    # "device" should still exist if save fails.
    assert "device" in registrations
