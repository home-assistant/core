"""Tests for the mobile_app HTTP API."""

from binascii import unhexlify
from http import HTTPStatus
import json
from unittest.mock import patch

from nacl.encoding import Base64Encoder
from nacl.secret import SecretBox

from homeassistant.components.mobile_app.const import CONF_SECRET, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import REGISTER, REGISTER_CLEARTEXT, RENDER_TEMPLATE

from tests.common import MockConfigEntry, MockUser
from tests.typing import ClientSessionGenerator


async def test_registration(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test that registrations happen."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    with patch(
        "homeassistant.components.person.async_add_user_device_tracker",
        spec=True,
    ) as add_user_dev_track:
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )

    assert len(add_user_dev_track.mock_calls) == 1
    assert add_user_dev_track.mock_calls[0][1][1] == hass_admin_user.id
    assert add_user_dev_track.mock_calls[0][1][2] == "device_tracker.test_1"

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    entries = hass.config_entries.async_entries(DOMAIN)

    assert entries[0].unique_id == "io.homeassistant.mobile_app_test-mock-device-id"
    assert entries[0].data["device_id"] == REGISTER_CLEARTEXT["device_id"]
    assert entries[0].data["app_data"] == REGISTER_CLEARTEXT["app_data"]
    assert entries[0].data["app_id"] == REGISTER_CLEARTEXT["app_id"]
    assert entries[0].data["app_name"] == REGISTER_CLEARTEXT["app_name"]
    assert entries[0].data["app_version"] == REGISTER_CLEARTEXT["app_version"]
    assert entries[0].data["device_name"] == REGISTER_CLEARTEXT["device_name"]
    assert entries[0].data["manufacturer"] == REGISTER_CLEARTEXT["manufacturer"]
    assert entries[0].data["model"] == REGISTER_CLEARTEXT["model"]
    assert entries[0].data["os_name"] == REGISTER_CLEARTEXT["os_name"]
    assert entries[0].data["os_version"] == REGISTER_CLEARTEXT["os_version"]
    assert (
        entries[0].data["supports_encryption"]
        == REGISTER_CLEARTEXT["supports_encryption"]
    )


async def test_reregistration(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test that reregistrations overwrite the current entry."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    extra_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="io.homeassistant.mobile_app_test-mock-device-id",
        data={
            "device_id": "mock-device-id",
            "app_data": {"foo": "bar"},
            "app_id": "io.homeassistant.mobile_app_test",
            "app_name": "Mobile App Tests",
            "app_version": "1.0.0",
            "device_name": "Test 1",
            "manufacturer": "mobile_app",
            "model": "Test",
            "os_name": "Linux",
            "os_version": "1.0",
            "supports_encryption": False,
            "webhook_id": "mock-webhook-id",
        },
    )
    extra_config_entry.add_to_hass(hass)
    second_extra_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="io.homeassistant.mobile_app_test-mock-device-id",
        data={
            "device_id": "mock-device-id",
            "app_data": {"foo": "bar"},
            "app_id": "io.homeassistant.mobile_app_test",
            "app_name": "Mobile App Tests",
            "app_version": "1.0.0",
            "device_name": "Test 1",
            "manufacturer": "mobile_app",
            "model": "Test",
            "os_name": "Linux",
            "os_version": "1.0",
            "supports_encryption": False,
            "webhook_id": "mock-webhook-id2",
        },
    )
    second_extra_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(extra_config_entry.entry_id)
    assert await hass.config_entries.async_setup(second_extra_config_entry.entry_id)

    api_client = await hass_client()

    entries = hass.config_entries.async_entries(DOMAIN)

    assert len(entries) == 2
    config_entry = entries[0]

    assert config_entry.unique_id == "io.homeassistant.mobile_app_test-mock-device-id"
    assert config_entry.state == ConfigEntryState.LOADED

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    assert config_entry.state == ConfigEntryState.LOADED

    entries = hass.config_entries.async_entries(DOMAIN)

    assert len(entries) == 2

    new_entry = entries[0]
    assert new_entry.unique_id == "io.homeassistant.mobile_app_test-mock-device-id"
    assert new_entry.entry_id != config_entry.entry_id
    assert new_entry.entry_id != extra_config_entry.entry_id
    assert new_entry.state == ConfigEntryState.LOADED


async def test_registration_encryption(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that registrations happen."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    resp = await api_client.post("/api/mobile_app/registrations", json=REGISTER)

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()

    key = unhexlify(register_json[CONF_SECRET])

    payload = json.dumps(RENDER_TEMPLATE["data"]).encode("utf-8")

    data = SecretBox(key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await api_client.post(
        f"/api/webhook/{register_json[CONF_WEBHOOK_ID]}", json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = SecretBox(key).decrypt(
        webhook_json["encrypted_data"], encoder=Base64Encoder
    )
    decrypted_data = decrypted_data.decode("utf-8")

    assert json.loads(decrypted_data) == {"one": "Hello world"}


async def test_registration_encryption_legacy(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that registrations happen."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    resp = await api_client.post("/api/mobile_app/registrations", json=REGISTER)

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()

    keylen = SecretBox.KEY_SIZE
    key = register_json[CONF_SECRET].encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b"\0")

    payload = json.dumps(RENDER_TEMPLATE["data"]).encode("utf-8")

    data = SecretBox(key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await api_client.post(
        f"/api/webhook/{register_json[CONF_WEBHOOK_ID]}", json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = SecretBox(key).decrypt(
        webhook_json["encrypted_data"], encoder=Base64Encoder
    )
    decrypted_data = decrypted_data.decode("utf-8")

    assert json.loads(decrypted_data) == {"one": "Hello world"}
