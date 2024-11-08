"""Test config entries API."""

from typing import Any

import pytest
from webauthn import base64url_to_bytes
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from homeassistant.auth.models import Credentials
from homeassistant.auth.providers import webauthn as provider_webauthn
from homeassistant.components.config import auth_provider_webauthn as auth_webauthn
from homeassistant.core import HomeAssistant

from tests.common import CLIENT_ID, MockUser
from tests.typing import WebSocketGenerator

AUTH_PROVIDER_TYPE = "webauthn"
TEST_RP_NAME = "Home Assistant"
TEST_USERNAME = "testuser"
TEST_USERNAME_2 = "testuser2"
TEST_RP_ID = "localhost"
TEST_EXPECTED_ORIGIN = "http://localhost:5000"
TEST_EXPECTED_CHALLENGE = "CeTWogmg0cchuiYuFrv8DXXdMZSIQRVZJOga_xayVVEcBj0Cw3y73yhD4FkGSe-RrP6hPJJAIm3LVien4hXELg"
DEFAULT_PASSKEY_NAME = "Home Assistant Passkey"
CREDENTIAL_NOT_FOUND_ERROR = {
    "code": "credential_not_found",
    "message": "Credential not found",
}


@pytest.fixture
def verificaton_credentials() -> dict[str, Any]:
    """Return credentials for verification."""
    return {
        "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
        "rawId": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
        "response": {
            "attestationObject": "o2NmbXRkbm9uZWdhdHRTdG10oGhhdXRoRGF0YVkBZ0mWDeWIDoxodDQXD2R2YFuP5K65ooYyx5lc87qDHZdjRQAAAAAAAAAAAAAAAAAAAAAAAAAAACBmggo_UlC8p2tiPVtNQ8nZ5NSxst4WS_5fnElA2viTq6QBAwM5AQAgWQEA31dtHqc70D_h7XHQ6V_nBs3Tscu91kBL7FOw56_VFiaKYRH6Z4KLr4J0S12hFJ_3fBxpKfxyMfK66ZMeAVbOl_wemY4S5Xs4yHSWy21Xm_dgWhLJjZ9R1tjfV49kDPHB_ssdvP7wo3_NmoUPYMgK-edgZ_ehttp_I6hUUCnVaTvn_m76b2j9yEPReSwl-wlGsabYG6INUhTuhSOqG-UpVVQdNJVV7GmIPHCA2cQpJBDZBohT4MBGme_feUgm4sgqVCWzKk6CzIKIz5AIVnspLbu05SulAVnSTB3NxTwCLNJR_9v9oSkvphiNbmQBVQH1tV_psyi9HM1Jtj9VJVKMeyFDAQAB",
            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIiwiY2hhbGxlbmdlIjoiQ2VUV29nbWcwY2NodWlZdUZydjhEWFhkTVpTSVFSVlpKT2dhX3hheVZWRWNCajBDdzN5NzN5aEQ0RmtHU2UtUnJQNmhQSkpBSW0zTFZpZW40aFhFTGciLCJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjUwMDAiLCJjcm9zc09yaWdpbiI6ZmFsc2V9",
            "transports": ["internal"],
        },
        "type": "public-key",
        "clientExtensionResults": {},
        "authenticatorAttachment": "platform",
    }


@pytest.fixture
def user_webauthn_credentials_data() -> dict[str, Any]:
    """Admin user webauthn credentials."""
    return {
        "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
        "username": "admin",
        "public_key": "pAEDAzkBACBZAQDfV20epzvQP-HtcdDpX-cGzdOxy73WQEvsU7Dnr9UWJophEfpngouvgnRLXaEUn_d8HGkp_HIx8rrpkx4BVs6X_B6ZjhLlezjIdJbLbVeb92BaEsmNn1HW2N9Xj2QM8cH-yx28_vCjf82ahQ9gyAr552Bn96G22n8jqFRQKdVpO-f-bvpvaP3IQ9F5LCX7CUaxptgbog1SFO6FI6ob5SlVVB00lVXsaYg8cIDZxCkkENkGiFPgwEaZ7995SCbiyCpUJbMqToLMgojPkAhWeyktu7TlK6UBWdJMHc3FPAIs0lH_2_2hKS-mGI1uZAFVAfW1X-mzKL0czUm2P1UlUox7IUMBAAE",
        "sign_count": "0",
        "name": DEFAULT_PASSKEY_NAME,
        "created_at": "2024-07-28T05:44:27.936070+00:00",
        "last_used_at": "2024-07-28T05:44:27.936077+00:00",
    }


@pytest.fixture
def auth_provider(hass: HomeAssistant) -> provider_webauthn.WebauthnAuthProvider:
    """Webauthn provider."""
    provider = provider_webauthn.WebauthnAuthProvider(
        hass,
        hass.auth._store,
        provider_webauthn.CONFIG_SCHEMA(
            {
                "type": AUTH_PROVIDER_TYPE,
                "rp_id": TEST_RP_ID,
                "rp_name": TEST_RP_NAME,
                "expected_origin": TEST_EXPECTED_ORIGIN,
            }
        ),
    )
    hass.auth._providers[provider.type] = provider
    return provider


@pytest.fixture(autouse=True)
async def setup_config(
    hass: HomeAssistant, auth_provider: provider_webauthn.WebauthnAuthProvider
) -> None:
    """Fixture that sets up the auth provider ."""
    auth_webauthn.async_setup(hass)


@pytest.fixture
async def owner_access_token(hass: HomeAssistant, hass_owner_user: MockUser) -> str:
    """Access token for owner user."""
    refresh_token = await hass.auth.async_create_refresh_token(
        hass_owner_user, CLIENT_ID
    )
    return hass.auth.async_create_access_token(refresh_token)


async def test_register_passkey(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: provider_webauthn.WebauthnAuthProvider,
    hass_admin_user: MockUser,
) -> None:
    """Test get registration options."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/passkey/register",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    options = response["result"]
    assert len(base64url_to_bytes(options.pop("challenge"))) == 64
    assert options == {
        "rp": {"name": TEST_RP_NAME, "id": TEST_RP_ID},
        "user": {
            "name": hass_admin_user.credentials[0].data["username"],
            "id": bytes_to_base64url(bytes.fromhex(hass_admin_user.id)),
            "displayName": hass_admin_user.name,
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": COSEAlgorithmIdentifier.ECDSA_SHA_256},
            {
                "type": "public-key",
                "alg": COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
            },
        ],
        "timeout": 60000,
        "excludeCredentials": [],
        "authenticatorSelection": {
            "requireResidentKey": False,
            "userVerification": "required",
        },
        "attestation": "none",
    }


async def test_register_verify_passkey(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: provider_webauthn.WebauthnAuthProvider,
    hass_admin_user: MockUser,
    verificaton_credentials: dict[str, Any],
) -> None:
    """Test verify registration."""
    await auth_provider.async_initialize()
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/passkey/register_verify",
            "credential": verificaton_credentials,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "invalid_user",
        "message": "Challenge not found",
    }

    auth_provider.data.add_registration(
        hass_admin_user.id,
        hass_admin_user.credentials[0].data["username"],
        TEST_EXPECTED_CHALLENGE,
    )
    assert len(hass_admin_user.credentials) == 1
    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/passkey/register_verify",
            "credential": verificaton_credentials,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert len(hass_admin_user.credentials) == 2
    webauthn_credential = hass_admin_user.credentials[1]
    assert webauthn_credential.auth_provider_type == AUTH_PROVIDER_TYPE
    assert set(webauthn_credential.data.keys()) == {
        "id",
        "username",
        "public_key",
        "sign_count",
        "name",
        "created_at",
        "last_used_at",
    }
    assert webauthn_credential.data["id"] == verificaton_credentials["id"]


async def test_remove_passkey(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: provider_webauthn.WebauthnAuthProvider,
    hass_admin_user: MockUser,
    user_webauthn_credentials_data: dict[str, Any],
) -> None:
    """Test remove passkey."""
    await auth_provider.async_initialize()
    hass_admin_user.add_to_auth_manager(hass.auth)
    webauthn_credentials = Credentials(
        auth_provider_id=None,
        auth_provider_type=AUTH_PROVIDER_TYPE,
        data=user_webauthn_credentials_data,
    )
    await auth_provider.store.async_link_user(hass_admin_user, webauthn_credentials)
    assert len(hass_admin_user.credentials) == 2

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/passkey/delete",
            "credential_id": webauthn_credentials.id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    assert len(hass_admin_user.credentials) == 1

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/passkey/delete",
            "credential_id": webauthn_credentials.id,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == CREDENTIAL_NOT_FOUND_ERROR


async def test_rename_passkey(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: provider_webauthn.WebauthnAuthProvider,
    hass_admin_user: MockUser,
    user_webauthn_credentials_data: dict[str, Any],
) -> None:
    """Test rename passkey."""
    await auth_provider.async_initialize()
    hass_admin_user.add_to_auth_manager(hass.auth)
    webauthn_credentials = Credentials(
        auth_provider_id=None,
        auth_provider_type=AUTH_PROVIDER_TYPE,
        data=user_webauthn_credentials_data,
    )
    await auth_provider.store.async_link_user(hass_admin_user, webauthn_credentials)
    assert len(hass_admin_user.credentials) == 2
    assert webauthn_credentials.data["name"] == DEFAULT_PASSKEY_NAME

    client = await hass_ws_client(hass)
    new_name = "New Name"
    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/passkey/rename",
            "credential_id": webauthn_credentials.id,
            "name": new_name,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert webauthn_credentials.data["name"] == new_name

    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/passkey/rename",
            "credential_id": "invalid_id",
            "name": new_name,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == CREDENTIAL_NOT_FOUND_ERROR


async def test_list_passkeys(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    auth_provider: provider_webauthn.WebauthnAuthProvider,
    hass_admin_user: MockUser,
    user_webauthn_credentials_data: dict[str, Any],
) -> None:
    """Test list passkeys."""
    await auth_provider.async_initialize()
    hass_admin_user.add_to_auth_manager(hass.auth)
    assert len(hass_admin_user.credentials) == 1

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "config/auth_provider/passkey/list",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    webauthn_credentials = Credentials(
        auth_provider_id=None,
        auth_provider_type=AUTH_PROVIDER_TYPE,
        data=user_webauthn_credentials_data,
    )
    await auth_provider.store.async_link_user(hass_admin_user, webauthn_credentials)
    assert len(hass_admin_user.credentials) == 2
    await client.send_json(
        {
            "id": 6,
            "type": "config/auth_provider/passkey/list",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "credential_id": webauthn_credentials.id,
            "id": webauthn_credentials.data["id"],
            "name": webauthn_credentials.data["name"],
            "created_at": webauthn_credentials.data["created_at"],
            "last_used_at": webauthn_credentials.data["last_used_at"],
        }
    ]
