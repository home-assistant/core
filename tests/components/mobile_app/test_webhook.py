"""Webhook tests for mobile_app."""
import logging

import pytest

from homeassistant.components.camera import SUPPORT_STREAM as CAMERA_SUPPORT_STREAM
from homeassistant.components.mobile_app.const import CONF_SECRET
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .const import CALL_SERVICE, FIRE_EVENT, REGISTER_CLEARTEXT, RENDER_TEMPLATE, UPDATE

from tests.async_mock import patch
from tests.common import async_mock_service

_LOGGER = logging.getLogger(__name__)


def encrypt_payload(secret_key, payload):
    """Return a encrypted payload given a key and dictionary of data."""
    try:
        from nacl.secret import SecretBox
        from nacl.encoding import Base64Encoder
    except (ImportError, OSError):
        pytest.skip("libnacl/libsodium is not installed")
        return

    import json

    keylen = SecretBox.KEY_SIZE
    prepped_key = secret_key.encode("utf-8")
    prepped_key = prepped_key[:keylen]
    prepped_key = prepped_key.ljust(keylen, b"\0")

    payload = json.dumps(payload).encode("utf-8")

    return (
        SecretBox(prepped_key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")
    )


def decrypt_payload(secret_key, encrypted_data):
    """Return a decrypted payload given a key and a string of encrypted data."""
    try:
        from nacl.secret import SecretBox
        from nacl.encoding import Base64Encoder
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


async def test_webhook_handle_render_template(create_registrations, webhook_client):
    """Test that we render templates properly."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json=RENDER_TEMPLATE,
    )

    assert resp.status == 200

    json = await resp.json()
    assert json == {"one": "Hello world"}


async def test_webhook_handle_call_services(hass, create_registrations, webhook_client):
    """Test that we call services properly."""
    calls = async_mock_service(hass, "test", "mobile_app")

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json=CALL_SERVICE,
    )

    assert resp.status == 200

    assert len(calls) == 1


async def test_webhook_handle_fire_event(hass, create_registrations, webhook_client):
    """Test that we can fire events."""
    events = []

    @callback
    def store_event(event):
        """Helepr to store events."""
        events.append(event)

    hass.bus.async_listen("test_event", store_event)

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]), json=FIRE_EVENT
    )

    assert resp.status == 200
    json = await resp.json()
    assert json == {}

    assert len(events) == 1
    assert events[0].data["hello"] == "yo world"


async def test_webhook_update_registration(webhook_client, authed_api_client):
    """Test that a we can update an existing registration via webhook."""
    register_resp = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )

    assert register_resp.status == 201
    register_json = await register_resp.json()

    webhook_id = register_json[CONF_WEBHOOK_ID]

    update_container = {"type": "update_registration", "data": UPDATE}

    update_resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}", json=update_container
    )

    assert update_resp.status == 200
    update_json = await update_resp.json()
    assert update_json["app_version"] == "2.0.0"
    assert CONF_WEBHOOK_ID not in update_json
    assert CONF_SECRET not in update_json


async def test_webhook_handle_get_zones(hass, create_registrations, webhook_client):
    """Test that we can get zones properly."""
    await async_setup_component(
        hass, ZONE_DOMAIN, {ZONE_DOMAIN: {}},
    )

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={"type": "get_zones"},
    )

    assert resp.status == 200

    json = await resp.json()
    assert len(json) == 1
    zones = sorted(json, key=lambda entry: entry["entity_id"])
    assert zones[0]["entity_id"] == "zone.home"


async def test_webhook_handle_get_config(hass, create_registrations, webhook_client):
    """Test that we can get config properly."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={"type": "get_config"},
    )

    assert resp.status == 200

    json = await resp.json()
    if "components" in json:
        json["components"] = set(json["components"])
    if "whitelist_external_dirs" in json:
        json["whitelist_external_dirs"] = set(json["whitelist_external_dirs"])

    hass_config = hass.config.as_dict()

    expected_dict = {
        "latitude": hass_config["latitude"],
        "longitude": hass_config["longitude"],
        "elevation": hass_config["elevation"],
        "unit_system": hass_config["unit_system"],
        "location_name": hass_config["location_name"],
        "time_zone": hass_config["time_zone"],
        "components": hass_config["components"],
        "version": hass_config["version"],
        "theme_color": "#03A9F4",  # Default frontend theme color
    }

    assert expected_dict == json


async def test_webhook_returns_error_incorrect_json(
    webhook_client, create_registrations, caplog
):
    """Test that an error is returned when JSON is invalid."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]), data="not json"
    )

    assert resp.status == 400
    json = await resp.json()
    assert json == {}
    assert "invalid JSON" in caplog.text


async def test_webhook_handle_decryption(webhook_client, create_registrations):
    """Test that we can encrypt/decrypt properly."""
    key = create_registrations[0]["secret"]
    data = encrypt_payload(key, RENDER_TEMPLATE["data"])

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]), json=container
    )

    assert resp.status == 200

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = decrypt_payload(key, webhook_json["encrypted_data"])

    assert decrypted_data == {"one": "Hello world"}


async def test_webhook_requires_encryption(webhook_client, create_registrations):
    """Test that encrypted registrations only accept encrypted data."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[0]["webhook_id"]),
        json=RENDER_TEMPLATE,
    )

    assert resp.status == 400

    webhook_json = await resp.json()
    assert "error" in webhook_json
    assert webhook_json["success"] is False
    assert webhook_json["error"]["code"] == "encryption_required"


async def test_webhook_update_location(hass, webhook_client, create_registrations):
    """Test that location can be updated."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {"gps": [1, 2], "gps_accuracy": 10, "altitude": -10},
        },
    )

    assert resp.status == 200

    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.attributes["latitude"] == 1.0
    assert state.attributes["longitude"] == 2.0
    assert state.attributes["gps_accuracy"] == 10
    assert state.attributes["altitude"] == -10


async def test_webhook_enable_encryption(hass, webhook_client, create_registrations):
    """Test that encryption can be added to a reg initially created without."""
    webhook_id = create_registrations[1]["webhook_id"]

    enable_enc_resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}", json={"type": "enable_encryption"},
    )

    assert enable_enc_resp.status == 200

    enable_enc_json = await enable_enc_resp.json()
    assert len(enable_enc_json) == 1
    assert CONF_SECRET in enable_enc_json

    key = enable_enc_json["secret"]

    enc_required_resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}", json=RENDER_TEMPLATE,
    )

    assert enc_required_resp.status == 400

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

    assert enc_resp.status == 200

    enc_json = await enc_resp.json()
    assert "encrypted_data" in enc_json

    decrypted_data = decrypt_payload(key, enc_json["encrypted_data"])

    assert decrypted_data == {"one": "Hello world"}


async def test_webhook_camera_stream_non_existent(
    hass, create_registrations, webhook_client
):
    """Test fetching camera stream URLs for a non-existent camera."""
    webhook_id = create_registrations[1]["webhook_id"]

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "stream_camera",
            "data": {"camera_entity_id": "camera.doesnt_exist"},
        },
    )

    assert resp.status == 400
    webhook_json = await resp.json()
    assert webhook_json["success"] is False


async def test_webhook_camera_stream_non_hls(
    hass, create_registrations, webhook_client
):
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

    assert resp.status == 200
    webhook_json = await resp.json()
    assert webhook_json["hls_path"] is None
    assert (
        webhook_json["mjpeg_path"]
        == "/api/camera_proxy_stream/camera.non_stream_camera"
    )


async def test_webhook_camera_stream_stream_available(
    hass, create_registrations, webhook_client
):
    """Test fetching camera stream URLs for an HLS/stream-supporting camera."""
    hass.states.async_set(
        "camera.stream_camera", "idle", {"supported_features": CAMERA_SUPPORT_STREAM}
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

    assert resp.status == 200
    webhook_json = await resp.json()
    assert webhook_json["hls_path"] == "/api/streams/some_hls_stream"
    assert webhook_json["mjpeg_path"] == "/api/camera_proxy_stream/camera.stream_camera"


async def test_webhook_camera_stream_stream_available_but_errors(
    hass, create_registrations, webhook_client
):
    """Test fetching camera stream URLs for an HLS/stream-supporting camera but that streaming errors."""
    hass.states.async_set(
        "camera.stream_camera", "idle", {"supported_features": CAMERA_SUPPORT_STREAM}
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

    assert resp.status == 200
    webhook_json = await resp.json()
    assert webhook_json["hls_path"] is None
    assert webhook_json["mjpeg_path"] == "/api/camera_proxy_stream/camera.stream_camera"
