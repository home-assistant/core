"""Webhook tests for mobile_app."""
from binascii import unhexlify
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.mobile_app.const import CONF_SECRET, DOMAIN
from homeassistant.components.tag import EVENT_TAG_SCANNED
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.const import (
    CONF_WEBHOOK_ID,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .const import CALL_SERVICE, FIRE_EVENT, REGISTER_CLEARTEXT, RENDER_TEMPLATE, UPDATE

from tests.common import async_capture_events, async_mock_service
from tests.components.conversation.conftest import mock_agent

# To avoid autoflake8 removing the import
mock_agent = mock_agent


@pytest.fixture
async def homeassistant(hass):
    """Load the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


def encrypt_payload(secret_key, payload, encode_json=True):
    """Return a encrypted payload given a key and dictionary of data."""
    try:
        from nacl.encoding import Base64Encoder
        from nacl.secret import SecretBox
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    prepped_key = unhexlify(secret_key)

    if encode_json:
        payload = json.dumps(payload)
    payload = payload.encode("utf-8")

    return (
        SecretBox(prepped_key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")
    )


def encrypt_payload_legacy(secret_key, payload, encode_json=True):
    """Return a encrypted payload given a key and dictionary of data."""
    try:
        from nacl.encoding import Base64Encoder
        from nacl.secret import SecretBox
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    keylen = SecretBox.KEY_SIZE
    prepped_key = secret_key.encode("utf-8")
    prepped_key = prepped_key[:keylen]
    prepped_key = prepped_key.ljust(keylen, b"\0")

    if encode_json:
        payload = json.dumps(payload)
    payload = payload.encode("utf-8")

    return (
        SecretBox(prepped_key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")
    )


def decrypt_payload(secret_key, encrypted_data):
    """Return a decrypted payload given a key and a string of encrypted data."""
    try:
        from nacl.encoding import Base64Encoder
        from nacl.secret import SecretBox
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    prepped_key = unhexlify(secret_key)

    decrypted_data = SecretBox(prepped_key).decrypt(
        encrypted_data, encoder=Base64Encoder
    )
    decrypted_data = decrypted_data.decode("utf-8")

    return json.loads(decrypted_data)


def decrypt_payload_legacy(secret_key, encrypted_data):
    """Return a decrypted payload given a key and a string of encrypted data."""
    try:
        from nacl.encoding import Base64Encoder
        from nacl.secret import SecretBox
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    keylen = SecretBox.KEY_SIZE
    prepped_key = secret_key.encode("utf-8")
    prepped_key = prepped_key[:keylen]
    prepped_key = prepped_key.ljust(keylen, b"\0")

    decrypted_data = SecretBox(prepped_key).decrypt(
        encrypted_data, encoder=Base64Encoder
    )
    decrypted_data = decrypted_data.decode("utf-8")

    return json.loads(decrypted_data)


async def test_webhook_handle_render_template(
    create_registrations, webhook_client
) -> None:
    """Test that we render templates properly."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "render_template",
            "data": {
                "one": {"template": "Hello world"},
                "two": {"template": "{{ now() | random }}"},
                "three": {"template": "{{ now() 3 }}"},
            },
        },
    )

    assert resp.status == HTTPStatus.OK

    json = await resp.json()
    assert json == {
        "one": "Hello world",
        "two": {"error": "TypeError: object of type 'datetime.datetime' has no len()"},
        "three": {
            "error": "TemplateSyntaxError: expected token 'end of print statement', got 'integer'"
        },
    }


async def test_webhook_handle_call_services(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that we call services properly."""
    calls = async_mock_service(hass, "test", "mobile_app")

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json=CALL_SERVICE,
    )

    assert resp.status == HTTPStatus.OK

    assert len(calls) == 1


async def test_webhook_handle_fire_event(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that we can fire events."""
    events = []

    @callback
    def store_event(event):
        """Help store events."""
        events.append(event)

    hass.bus.async_listen("test_event", store_event)

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]), json=FIRE_EVENT
    )

    assert resp.status == HTTPStatus.OK
    json = await resp.json()
    assert json == {}

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"


async def test_webhook_update_registration(webhook_client) -> None:
    """Test that a we can update an existing registration via webhook."""
    register_resp = await webhook_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )

    assert register_resp.status == HTTPStatus.CREATED
    register_json = await register_resp.json()

    webhook_id = register_json[CONF_WEBHOOK_ID]

    update_container = {"type": "update_registration", "data": UPDATE}

    update_resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}", json=update_container
    )

    assert update_resp.status == HTTPStatus.OK
    update_json = await update_resp.json()
    assert update_json["app_version"] == "2.0.0"
    assert CONF_WEBHOOK_ID not in update_json
    assert CONF_SECRET not in update_json


async def test_webhook_handle_get_zones(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that we can get zones properly."""
    # Zone is already loaded as part of the fixture,
    # so we just trigger a reload.
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            ZONE_DOMAIN: [
                {
                    "name": "School",
                    "latitude": 32.8773367,
                    "longitude": -117.2494053,
                    "radius": 250,
                    "icon": "mdi:school",
                },
                {
                    "name": "Work",
                    "latitude": 33.8773367,
                    "longitude": -118.2494053,
                },
            ]
        },
    ):
        await hass.services.async_call(ZONE_DOMAIN, "reload", blocking=True)

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={"type": "get_zones"},
    )

    assert resp.status == HTTPStatus.OK

    json = await resp.json()
    assert len(json) == 3
    zones = sorted(json, key=lambda entry: entry["entity_id"])
    assert zones[0]["entity_id"] == "zone.home"

    assert zones[1]["entity_id"] == "zone.school"
    assert zones[1]["attributes"]["icon"] == "mdi:school"
    assert zones[1]["attributes"]["latitude"] == 32.8773367
    assert zones[1]["attributes"]["longitude"] == -117.2494053
    assert zones[1]["attributes"]["radius"] == 250

    assert zones[2]["entity_id"] == "zone.work"
    assert "icon" not in zones[2]["attributes"]
    assert zones[2]["attributes"]["latitude"] == 33.8773367
    assert zones[2]["attributes"]["longitude"] == -118.2494053


async def test_webhook_handle_get_config(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that we can get config properly."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Create two entities
    for sensor in (
        {
            "name": "Battery State",
            "type": "sensor",
            "unique_id": "battery-state-id",
        },
        {
            "name": "Battery Charging",
            "type": "sensor",
            "unique_id": "battery-charging-id",
            "disabled": True,
        },
    ):
        reg_resp = await webhook_client.post(
            webhook_url,
            json={"type": "register_sensor", "data": sensor},
        )
        assert reg_resp.status == HTTPStatus.CREATED

    resp = await webhook_client.post(webhook_url, json={"type": "get_config"})

    assert resp.status == HTTPStatus.OK

    json = await resp.json()
    if "components" in json:
        json["components"] = set(json["components"])
    if "allowlist_external_dirs" in json:
        json["allowlist_external_dirs"] = set(json["allowlist_external_dirs"])

    hass_config = hass.config.as_dict()

    expected_dict = {
        "latitude": hass_config["latitude"],
        "longitude": hass_config["longitude"],
        "elevation": hass_config["elevation"],
        "unit_system": hass_config["unit_system"],
        "location_name": hass_config["location_name"],
        "time_zone": hass_config["time_zone"],
        "components": set(hass_config["components"]),
        "version": hass_config["version"],
        "theme_color": "#03A9F4",  # Default frontend theme color
        "entities": {
            "mock-device-id": {"disabled": False},
            "battery-state-id": {"disabled": False},
            "battery-charging-id": {"disabled": True},
        },
    }

    assert expected_dict == json


async def test_webhook_returns_error_incorrect_json(
    webhook_client, create_registrations, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an error is returned when JSON is invalid."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]), data="not json"
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    json = await resp.json()
    assert json == {}
    assert "invalid JSON" in caplog.text


@pytest.mark.parametrize(
    ("msg", "generate_response"),
    (
        (RENDER_TEMPLATE, lambda hass: {"one": "Hello world"}),
        (
            {"type": "get_zones", "data": {}},
            lambda hass: [hass.states.get("zone.home").as_dict()],
        ),
    ),
)
async def test_webhook_handle_decryption(
    hass: HomeAssistant, webhook_client, create_registrations, msg, generate_response
) -> None:
    """Test that we can encrypt/decrypt properly."""
    key = create_registrations[0]["secret"]
    data = encrypt_payload(key, msg["data"])

    container = {"type": msg["type"], "encrypted": True, "encrypted_data": data}

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = decrypt_payload(key, webhook_json["encrypted_data"])

    assert decrypted_data == generate_response(hass)


async def test_webhook_handle_decryption_legacy(
    webhook_client, create_registrations
) -> None:
    """Test that we can encrypt/decrypt properly."""
    key = create_registrations[0]["secret"]
    data = encrypt_payload_legacy(key, RENDER_TEMPLATE["data"])

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = decrypt_payload_legacy(key, webhook_json["encrypted_data"])

    assert decrypted_data == {"one": "Hello world"}


async def test_webhook_handle_decryption_fail(
    webhook_client, create_registrations, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we can encrypt/decrypt properly."""
    key = create_registrations[0]["secret"]

    # Send valid data
    data = encrypt_payload(key, RENDER_TEMPLATE["data"])
    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    webhook_json = await resp.json()
    decrypted_data = decrypt_payload(key, webhook_json["encrypted_data"])
    assert decrypted_data == {"one": "Hello world"}
    caplog.clear()

    # Send invalid JSON data
    data = encrypt_payload(key, "{not_valid", encode_json=False)
    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {}
    assert "Ignoring invalid JSON in encrypted payload" in caplog.text
    caplog.clear()

    # Break the key, and send JSON data
    data = encrypt_payload(key[::-1], RENDER_TEMPLATE["data"])
    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {}
    assert "Ignoring encrypted payload because unable to decrypt" in caplog.text


async def test_webhook_handle_decryption_legacy_fail(
    webhook_client, create_registrations, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that we can encrypt/decrypt properly."""
    key = create_registrations[0]["secret"]

    # Send valid data using legacy method
    data = encrypt_payload_legacy(key, RENDER_TEMPLATE["data"])
    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    webhook_json = await resp.json()
    decrypted_data = decrypt_payload_legacy(key, webhook_json["encrypted_data"])
    assert decrypted_data == {"one": "Hello world"}
    caplog.clear()

    # Send invalid JSON data
    data = encrypt_payload_legacy(key, "{not_valid", encode_json=False)
    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {}
    assert "Ignoring invalid JSON in encrypted payload" in caplog.text
    caplog.clear()

    # Break the key, and send JSON data
    data = encrypt_payload_legacy(key[::-1], RENDER_TEMPLATE["data"])
    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {}
    assert "Ignoring encrypted payload because unable to decrypt" in caplog.text


async def test_webhook_handle_decryption_legacy_upgrade(
    webhook_client, create_registrations
) -> None:
    """Test that we can encrypt/decrypt properly."""
    key = create_registrations[0]["secret"]

    # Send using legacy method
    data = encrypt_payload_legacy(key, RENDER_TEMPLATE["data"])

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = decrypt_payload_legacy(key, webhook_json["encrypted_data"])

    assert decrypted_data == {"one": "Hello world"}

    # Send using new method
    data = encrypt_payload(key, RENDER_TEMPLATE["data"])

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = decrypt_payload(key, webhook_json["encrypted_data"])

    assert decrypted_data == {"one": "Hello world"}

    # Send using legacy method - no longer possible
    data = encrypt_payload_legacy(key, RENDER_TEMPLATE["data"])

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {}


async def test_webhook_requires_encryption(
    webhook_client, create_registrations
) -> None:
    """Test that encrypted registrations only accept encrypted data."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]),
        json=RENDER_TEMPLATE,
    )

    assert resp.status == HTTPStatus.BAD_REQUEST

    webhook_json = await resp.json()
    assert "error" in webhook_json
    assert webhook_json["success"] is False
    assert webhook_json["error"]["code"] == "encryption_required"


async def test_webhook_update_location_without_locations(
    hass: HomeAssistant, webhook_client, create_registrations
) -> None:
    """Test that location can be updated."""

    # start off with a location set by name
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"location_name": STATE_HOME},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == STATE_HOME

    # set location to an 'unknown' state
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"altitude": 123},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["altitude"] == 123


async def test_webhook_update_location_with_gps(
    hass: HomeAssistant, webhook_client, create_registrations
) -> None:
    """Test that location can be updated."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"gps": [1, 2], "gps_accuracy": 10, "altitude": -10},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.attributes["latitude"] == 1.0
    assert state.attributes["longitude"] == 2.0
    assert state.attributes["gps_accuracy"] == 10
    assert state.attributes["altitude"] == -10


async def test_webhook_update_location_with_gps_without_accuracy(
    hass: HomeAssistant, webhook_client, create_registrations
) -> None:
    """Test that location can be updated."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"gps": [1, 2]},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state.state == STATE_UNKNOWN


async def test_webhook_update_location_with_location_name(
    hass: HomeAssistant, webhook_client, create_registrations
) -> None:
    """Test that location can be updated."""

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            ZONE_DOMAIN: [
                {
                    "name": "zone_name",
                    "latitude": 1.23,
                    "longitude": -4.56,
                    "radius": 200,
                    "icon": "mdi:test-tube",
                },
            ]
        },
    ):
        await hass.services.async_call(ZONE_DOMAIN, "reload", blocking=True)

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"location_name": "zone_name"},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state.state == "zone_name"

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"location_name": STATE_HOME},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state.state == STATE_HOME

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"location_name": STATE_NOT_HOME},
        },
    )

    assert resp.status == HTTPStatus.OK

    state = hass.states.get("device_tracker.test_1_2")
    assert state.state == STATE_NOT_HOME


async def test_webhook_enable_encryption(
    hass: HomeAssistant, webhook_client, create_registrations
) -> None:
    """Test that encryption can be added to a reg initially created without."""
    webhook_id = create_registrations[1]["webhook_id"]

    enable_enc_resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={"type": "enable_encryption"},
    )

    assert enable_enc_resp.status == HTTPStatus.OK

    enable_enc_json = await enable_enc_resp.json()
    assert len(enable_enc_json) == 1
    assert CONF_SECRET in enable_enc_json

    key = enable_enc_json["secret"]

    enc_required_resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json=RENDER_TEMPLATE,
    )

    assert enc_required_resp.status == HTTPStatus.BAD_REQUEST

    enc_required_json = await enc_required_resp.json()
    assert "error" in enc_required_json
    assert enc_required_json["success"] is False
    assert enc_required_json["error"]["code"] == "encryption_required"

    enc_data = encrypt_payload(key, RENDER_TEMPLATE["data"])

    container = {
        "type": "render_template",
        "encrypted": True,
        "encrypted_data": enc_data,
    }

    enc_resp = await webhook_client.post(f"/api/webhook/{webhook_id}", json=container)

    assert enc_resp.status == HTTPStatus.OK

    enc_json = await enc_resp.json()
    assert "encrypted_data" in enc_json

    decrypted_data = decrypt_payload(key, enc_json["encrypted_data"])

    assert decrypted_data == {"one": "Hello world"}


async def test_webhook_camera_stream_non_existent(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test fetching camera stream URLs for a non-existent camera."""
    webhook_id = create_registrations[1]["webhook_id"]

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "stream_camera",
            "data": {"camera_entity_id": "camera.doesnt_exist"},
        },
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    webhook_json = await resp.json()
    assert webhook_json["success"] is False


async def test_webhook_camera_stream_non_hls(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test fetching camera stream URLs for a non-HLS/stream-supporting camera."""
    hass.states.async_set("camera.non_stream_camera", "idle", {"supported_features": 0})

    webhook_id = create_registrations[1]["webhook_id"]

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "stream_camera",
            "data": {"camera_entity_id": "camera.non_stream_camera"},
        },
    )

    assert resp.status == HTTPStatus.OK
    webhook_json = await resp.json()
    assert webhook_json["hls_path"] is None
    assert (
        webhook_json["mjpeg_path"]
        == "/api/camera_proxy_stream/camera.non_stream_camera"
    )


async def test_webhook_camera_stream_stream_available(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test fetching camera stream URLs for an HLS/stream-supporting camera."""
    hass.states.async_set(
        "camera.stream_camera",
        "idle",
        {"supported_features": CameraEntityFeature.STREAM},
    )

    webhook_id = create_registrations[1]["webhook_id"]

    with patch(
        "homeassistant.components.camera.async_request_stream",
        return_value="/api/streams/some_hls_stream",
    ):
        resp = await webhook_client.post(
            f"/api/webhook/{webhook_id}",
            json={
                "type": "stream_camera",
                "data": {"camera_entity_id": "camera.stream_camera"},
            },
        )

    assert resp.status == HTTPStatus.OK
    webhook_json = await resp.json()
    assert webhook_json["hls_path"] == "/api/streams/some_hls_stream"
    assert webhook_json["mjpeg_path"] == "/api/camera_proxy_stream/camera.stream_camera"


async def test_webhook_camera_stream_stream_available_but_errors(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test fetching camera stream URLs for an HLS/stream-supporting camera but that streaming errors."""
    hass.states.async_set(
        "camera.stream_camera",
        "idle",
        {"supported_features": CameraEntityFeature.STREAM},
    )

    webhook_id = create_registrations[1]["webhook_id"]

    with patch(
        "homeassistant.components.camera.async_request_stream",
        side_effect=HomeAssistantError(),
    ):
        resp = await webhook_client.post(
            f"/api/webhook/{webhook_id}",
            json={
                "type": "stream_camera",
                "data": {"camera_entity_id": "camera.stream_camera"},
            },
        )

    assert resp.status == HTTPStatus.OK
    webhook_json = await resp.json()
    assert webhook_json["hls_path"] is None
    assert webhook_json["mjpeg_path"] == "/api/camera_proxy_stream/camera.stream_camera"


async def test_webhook_handle_scan_tag(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_registrations,
    webhook_client,
) -> None:
    """Test that we can scan tags."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "mock-device-id")})
    assert device is not None

    events = async_capture_events(hass, EVENT_TAG_SCANNED)

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={"type": "scan_tag", "data": {"tag_id": "mock-tag-id"}},
    )

    assert resp.status == HTTPStatus.OK
    json = await resp.json()
    assert json == {}

    assert len(events) == 1
    assert events[0].data["tag_id"] == "mock-tag-id"
    assert events[0].data["device_id"] == device.id


async def test_register_sensor_limits_state_class(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that we limit state classes to sensors only."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "state_class": "total",
                "unique_id": "abcd",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "binary_sensor",
                "state_class": "total",
                "unique_id": "efgh",
            },
        },
    )

    # This means it was ignored.
    assert reg_resp.status == HTTPStatus.OK


async def test_reregister_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations,
    webhook_client,
) -> None:
    """Test that we can add more info in re-registration."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "abcd",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    entry = entity_registry.async_get("sensor.test_1_battery_state")
    assert entry.original_name == "Test 1 Battery State"
    assert entry.device_class is None
    assert entry.unit_of_measurement is None
    assert entry.entity_category is None
    assert entry.original_icon == "mdi:cellphone"
    assert entry.disabled_by is None

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "New Name",
                "state": 100,
                "type": "sensor",
                "unique_id": "abcd",
                "state_class": "measurement",
                "device_class": "battery",
                "entity_category": "diagnostic",
                "icon": "mdi:new-icon",
                "unit_of_measurement": "%",
                "disabled": True,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    entry = entity_registry.async_get("sensor.test_1_battery_state")
    assert entry.original_name == "Test 1 New Name"
    assert entry.device_class == "battery"
    assert entry.unit_of_measurement == "%"
    assert entry.entity_category == "diagnostic"
    assert entry.original_icon == "mdi:new-icon"
    assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "New Name",
                "type": "sensor",
                "unique_id": "abcd",
                "disabled": False,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    entry = entity_registry.async_get("sensor.test_1_battery_state")
    assert entry.disabled_by is None

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "New Name 2",
                "state": 100,
                "type": "sensor",
                "unique_id": "abcd",
                "state_class": None,
                "device_class": None,
                "entity_category": None,
                "icon": None,
                "unit_of_measurement": None,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    entry = entity_registry.async_get("sensor.test_1_battery_state")
    assert entry.original_name == "Test 1 New Name 2"
    assert entry.device_class is None
    assert entry.unit_of_measurement is None
    assert entry.entity_category is None
    assert entry.original_icon is None


async def test_webhook_handle_conversation_process(
    hass: HomeAssistant, homeassistant, create_registrations, webhook_client, mock_agent
) -> None:
    """Test that we can converse."""
    webhook_client.server.app.router._frozen = False

    with patch(
        "homeassistant.components.conversation.AgentManager.async_get_agent",
        return_value=mock_agent,
    ):
        resp = await webhook_client.post(
            "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
            json={
                "type": "conversation_process",
                "data": {
                    "text": "Turn the kitchen light off",
                },
            },
        )

    assert resp.status == HTTPStatus.OK
    json = await resp.json()
    assert json == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Test response",
                }
            },
            "language": hass.config.language,
            "data": {
                "targets": [],
                "success": [],
                "failed": [],
            },
        },
        "conversation_id": None,
    }


async def test_sending_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations,
    webhook_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we can register and send sensor state as number and None."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "abcd",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery Health",
                "state": "good",
                "type": "sensor",
                "unique_id": "health-id",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    entry = entity_registry.async_get("sensor.test_1_battery_state")
    assert entry.original_name == "Test 1 Battery State"
    assert entry.device_class is None
    assert entry.unit_of_measurement is None
    assert entry.entity_category is None
    assert entry.original_icon == "mdi:cellphone"
    assert entry.disabled_by is None

    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_1_battery_state")
    assert state is not None
    assert state.state == "100"

    state = hass.states.get("sensor.test_1_battery_health")
    assert state is not None
    assert state.state == "good"

    # Now with a list.
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "state": 50.0000,
                    "type": "sensor",
                    "unique_id": "abcd",
                },
                {
                    "state": "okay-ish",
                    "type": "sensor",
                    "unique_id": "health-id",
                },
            ],
        },
    )

    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_1_battery_state")
    assert state is not None
    assert state.state == "50.0"

    state = hass.states.get("sensor.test_1_battery_health")
    assert state is not None
    assert state.state == "okay-ish"
