"""Tests for mobile_app component."""
# pylint: disable=redefined-outer-name,unused-import
import pytest

from homeassistant.components.mobile_app.const import DOMAIN
from homeassistant.setup import async_setup_component

from .const import REGISTER, REGISTER_CLEARTEXT

from tests.common import mock_device_registry


@pytest.fixture
def registry(hass):
    """Return a configured device registry."""
    return mock_device_registry(hass)


@pytest.fixture
async def create_registrations(hass, authed_api_client):
    """Return two new registrations."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    enc_reg = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER
    )

    assert enc_reg.status == 201
    enc_reg_json = await enc_reg.json()

    clear_reg = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )

    assert clear_reg.status == 201
    clear_reg_json = await clear_reg.json()

    await hass.async_block_till_done()

    return (enc_reg_json, clear_reg_json)


@pytest.fixture
async def webhook_client(hass, authed_api_client, aiohttp_client):
    """mobile_app mock client."""
    # We pass in the authed_api_client server instance because
    # it is used inside create_registrations and just passing in
    # the app instance would cause the server to start twice,
    # which caused deprecation warnings to be printed.
    return await aiohttp_client(authed_api_client.server)


@pytest.fixture
async def authed_api_client(hass, hass_client):
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return await hass_client()


@pytest.fixture(autouse=True)
async def setup_ws(hass):
    """Configure the websocket_api component."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()


@pytest.fixture
async def encrypt_payload():
    """Return a encrypted payload given a key and dictionary of data."""

    def do_encrypt(secret_key, payload):
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
            SecretBox(prepped_key)
            .encrypt(payload, encoder=Base64Encoder)
            .decode("utf-8")
        )

    return do_encrypt


@pytest.fixture
async def decrypt_payload():
    """Return a decrypted payload given a key and a string of encrypted data."""

    def do_decrypt(secret_key, encrypted_data):
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

    return do_decrypt
