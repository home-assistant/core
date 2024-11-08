"""Test the Webauthn auth provider."""

from typing import Any

import pytest
import voluptuous as vol

from homeassistant import auth, data_entry_flow
from homeassistant.auth import auth_store
from homeassistant.auth.models import Credentials, User
from homeassistant.auth.providers import webauthn as auth_webauthn
from homeassistant.core import HomeAssistant

AUTH_PROVIDER_TYPE = "webauthn"
TEST_RP_NAME = "Home Assistant"
TEST_USERNAME = "testuser"
TEST_USERNAME_2 = "testuser2"
TEST_RP_ID = "localhost"
TEST_CHALLENGE = "iPmAi1Pp1XL6oAgq3PWZtZPnZa1zFUDoGbaQ0_KvVG1lF2s3Rt_3o4uSzccy0tmcTIpTTT4BU1T-I4maavndjQ"
TEST_EXPECTED_ORIGIN = "http://localhost:5000"


@pytest.fixture
async def store(hass: HomeAssistant) -> auth_store.AuthStore:
    """Test store."""
    store = auth_store.AuthStore(hass)
    await store.async_load()
    return store


@pytest.fixture
def data(hass: HomeAssistant) -> auth_webauthn.Data:
    """Create a loaded data class."""
    data = auth_webauthn.Data(hass)
    hass.loop.run_until_complete(data.async_load())
    return data


@pytest.fixture
async def user(store: auth_store.AuthStore) -> User:
    """Test user."""

    ha_credential = Credentials(
        auth_provider_id=None,
        auth_provider_type="homeassistant",
        data={"username": TEST_USERNAME},
    )
    return await store.async_create_user(
        name="Test User",
        is_owner=True,
        is_active=True,
        credentials=ha_credential,
        system_generated=False,
        local_only=False,
    )


@pytest.fixture
async def user_with_credentials(store: auth_store.AuthStore):
    """Test user with credentials."""
    ha_credential = Credentials(
        auth_provider_id=None,
        auth_provider_type="homeassistant",
        data={"username": TEST_USERNAME_2},
    )
    webuathn_credential = Credentials(
        auth_provider_id=None,
        auth_provider_type="webauthn",
        data={
            "username": TEST_USERNAME_2,
            "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
            "public_key": "pAEDAzkBACBZAQDfV20epzvQP-HtcdDpX-cGzdOxy73WQEvsU7Dnr9UWJophEfpngouvgnRLXaEUn_d8HGkp_HIx8rrpkx4BVs6X_B6ZjhLlezjIdJbLbVeb92BaEsmNn1HW2N9Xj2QM8cH-yx28_vCjf82ahQ9gyAr552Bn96G22n8jqFRQKdVpO-f-bvpvaP3IQ9F5LCX7CUaxptgbog1SFO6FI6ob5SlVVB00lVXsaYg8cIDZxCkkENkGiFPgwEaZ7995SCbiyCpUJbMqToLMgojPkAhWeyktu7TlK6UBWdJMHc3FPAIs0lH_2_2hKS-mGI1uZAFVAfW1X-mzKL0czUm2P1UlUox7IUMBAAE",
            "name": "test_name",
            "sign_count": 0,
            "created_at": "2024-07-25T08:22:20.910967+00:00",
            "last_used_at": "2024-07-25T08:23:38.865949+00:00",
        },
    )
    user = await store.async_create_user(
        "Test User 2", True, True, False, ha_credential, local_only=False
    )
    await store.async_link_user(user, webuathn_credential)
    return user


@pytest.fixture
def provider(
    hass: HomeAssistant, store: auth_store.AuthStore
) -> auth_webauthn.WebauthnAuthProvider:
    """Mock provider."""
    return auth_webauthn.WebauthnAuthProvider(
        hass,
        store,
        auth_webauthn.CONFIG_SCHEMA(
            {
                "type": AUTH_PROVIDER_TYPE,
                "rp_id": TEST_RP_ID,
                "rp_name": TEST_RP_NAME,
                "expected_origin": TEST_EXPECTED_ORIGIN,
            }
        ),
    )


@pytest.fixture
def manager(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    provider: auth_webauthn.WebauthnAuthProvider,
) -> auth.AuthManager:
    """Mock manager."""
    return auth.AuthManager(hass, store, {(provider.type, provider.id): provider}, {})


@pytest.fixture
def auth_credential() -> dict[str, Any]:
    """Return a valid auth credential."""
    return {
        "id": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
        "rawId": "ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
        "response": {
            "authenticatorData": "SZYN5YgOjGh0NBcPZHZgW4_krrmihjLHmVzzuoMdl2MFAAAAAQ",
            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0IiwiY2hhbGxlbmdlIjoiaVBtQWkxUHAxWEw2b0FncTNQV1p0WlBuWmExekZVRG9HYmFRMF9LdlZHMWxGMnMzUnRfM280dVN6Y2N5MHRtY1RJcFRUVDRCVTFULUk0bWFhdm5kalEiLCJvcmlnaW4iOiJodHRwOi8vbG9jYWxob3N0OjUwMDAiLCJjcm9zc09yaWdpbiI6ZmFsc2V9",
            "signature": "iOHKX3erU5_OYP_r_9HLZ-CexCE4bQRrxM8WmuoKTDdhAnZSeTP0sjECjvjfeS8MJzN1ArmvV0H0C3yy_FdRFfcpUPZzdZ7bBcmPh1XPdxRwY747OrIzcTLTFQUPdn1U-izCZtP_78VGw9pCpdMsv4CUzZdJbEcRtQuRS03qUjqDaovoJhOqEBmxJn9Wu8tBi_Qx7A33RbYjlfyLm_EDqimzDZhyietyop6XUcpKarKqVH0M6mMrM5zTjp8xf3W7odFCadXEJg-ERZqFM0-9Uup6kJNLbr6C5J4NDYmSm3HCSA6lp2iEiMPKU8Ii7QZ61kybXLxsX4w4Dm3fOLjmDw",
            "userHandle": "T1RWa1l6VXdPRFV0WW1NNVlTMDBOVEkxTFRnd056Z3RabVZpWVdZNFpEVm1ZMk5p",
        },
        "type": "public-key",
        "authenticatorAttachment": "cross-platform",
        "clientExtensionResults": {},
    }


async def test_config_schema() -> None:
    """Test configuration schema."""
    with pytest.raises(vol.Invalid):
        auth_webauthn.CONFIG_SCHEMA({})

    with pytest.raises(vol.Invalid):
        auth_webauthn.CONFIG_SCHEMA({"type": AUTH_PROVIDER_TYPE})

    with pytest.raises(vol.Invalid):
        auth_webauthn.CONFIG_SCHEMA({"type": AUTH_PROVIDER_TYPE, "rp_id": TEST_RP_ID})

    with pytest.raises(vol.Invalid):
        auth_webauthn.CONFIG_SCHEMA(
            {"type": AUTH_PROVIDER_TYPE, "rp_id": TEST_RP_ID, "rp_name": "Test RP"}
        )

    assert auth_webauthn.CONFIG_SCHEMA(
        {
            "type": AUTH_PROVIDER_TYPE,
            "rp_id": TEST_RP_ID,
            "expected_origin": TEST_EXPECTED_ORIGIN,
        }
    )

    assert auth_webauthn.CONFIG_SCHEMA(
        {
            "type": AUTH_PROVIDER_TYPE,
            "rp_id": TEST_RP_ID,
            "rp_name": "Test RP",
            "expected_origin": TEST_EXPECTED_ORIGIN,
        }
    )


async def test_login_flow_generate_options(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    user: User,
    user_with_credentials: User,
) -> None:
    """Test login flow."""
    provider = auth_webauthn.WebauthnAuthProvider(
        hass,
        store,
        auth_webauthn.CONFIG_SCHEMA(
            {
                "type": AUTH_PROVIDER_TYPE,
                "rp_id": TEST_RP_ID,
                "rp_name": TEST_RP_NAME,
                "expected_origin": TEST_EXPECTED_ORIGIN,
            }
        ),
    )
    await provider.async_initialize()
    provider.data.add_registration(user.id, TEST_USERNAME, "")
    provider.data.add_registration(user_with_credentials.id, TEST_USERNAME_2, "")

    flow = await provider.async_login_flow({})
    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await flow.async_step_init({"username": "test-tuser"})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_user"

    result = await flow.async_step_init({"username": TEST_USERNAME})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "challenge"
    assert result["description_placeholders"]["webauthn_options"]["challenge"]
    assert result["description_placeholders"]["webauthn_options"]["rpId"] == TEST_RP_ID
    assert (
        len(result["description_placeholders"]["webauthn_options"]["allowCredentials"])
        == 0
    )

    result = await flow.async_step_init({"username": TEST_USERNAME_2})
    assert (
        len(result["description_placeholders"]["webauthn_options"]["allowCredentials"])
        == 1
    )


async def test_login_flow_finish(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    user: User,
    user_with_credentials: User,
    auth_credential: dict[str, Any],
) -> None:
    """Test finish login flow."""
    provider = auth_webauthn.WebauthnAuthProvider(
        hass,
        store,
        auth_webauthn.CONFIG_SCHEMA(
            {
                "type": AUTH_PROVIDER_TYPE,
                "rp_id": TEST_RP_ID,
                "rp_name": TEST_RP_NAME,
                "expected_origin": TEST_EXPECTED_ORIGIN,
            }
        ),
    )
    await provider.async_initialize()
    provider.data.add_registration(user.id, TEST_USERNAME, "")
    provider.data.add_registration(user_with_credentials.id, TEST_USERNAME_2, "")

    flow = await provider.async_login_flow({})
    flow.user = user_with_credentials
    result = await flow.async_step_challenge()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "challenge"
    assert result["errors"]["base"] == "invalid_auth"

    result = await flow.async_step_challenge({"authentication_credential": {}})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "challenge"
    assert result["errors"]["base"] == "invalid_user"

    result = await flow.async_step_challenge(
        {"authentication_credential": auth_credential}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "challenge"
    assert result["errors"]["base"] == "invalid_challenge"

    provider.data.add_challenge(user_with_credentials.id, TEST_CHALLENGE)
    result = await flow.async_step_challenge(
        {"authentication_credential": auth_credential}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    provider2 = auth_webauthn.WebauthnAuthProvider(
        hass,
        store,
        auth_webauthn.CONFIG_SCHEMA(
            {
                "type": AUTH_PROVIDER_TYPE,
                "rp_id": TEST_RP_ID,
                "rp_name": TEST_RP_NAME,
                "expected_origin": "http://localhost:5001",
            }
        ),
    )
    await provider2.async_initialize()
    provider2.data.add_registration(
        user_with_credentials.id, TEST_USERNAME_2, TEST_CHALLENGE
    )
    flow = await provider2.async_login_flow({})
    flow.user = user_with_credentials
    result = await flow.async_step_challenge(
        {"authentication_credential": auth_credential}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "challenge"
    assert result["errors"]["base"] == "invalid_challenge"


async def test_get_or_create_credentials(
    hass: HomeAssistant,
    store: auth_store.AuthStore,
    user_with_credentials: User,
    auth_credential: dict[str, Any],
) -> None:
    """Test get or create credentials."""
    provider = auth_webauthn.WebauthnAuthProvider(
        hass,
        store,
        auth_webauthn.CONFIG_SCHEMA(
            {
                "type": AUTH_PROVIDER_TYPE,
                "rp_id": TEST_RP_ID,
                "rp_name": TEST_RP_NAME,
                "expected_origin": TEST_EXPECTED_ORIGIN,
            }
        ),
    )
    await provider.async_initialize()
    provider.data.add_registration(
        user_with_credentials.id, TEST_USERNAME, TEST_CHALLENGE
    )

    with pytest.raises(auth_webauthn.InvalidUser):
        credentials = await provider.async_get_or_create_credentials(
            {"authentication_credential": {"id": "invalid"}}
        )

    with pytest.raises(auth_webauthn.InvalidAuth):
        credentials = await provider.async_get_or_create_credentials(
            {"authentication_credential": {}}
        )

    credentials = await provider.async_get_or_create_credentials(
        {"authentication_credential": auth_credential}
    )
    assert credentials is user_with_credentials.credentials[1]
    assert user_with_credentials.credentials[1].auth_provider_type == AUTH_PROVIDER_TYPE
