"""Test the Aladdin Connect Garage Door config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.aladdin_connect.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
USER_ID = "test_user_123"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
async def access_token(hass: HomeAssistant) -> str:
    """Return a valid access token with sub field for unique ID."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": USER_ID,
            "aud": [],
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
        },
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
    access_token,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.aladdin_connect.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.unique_id == USER_ID
    assert config_entry.title == "Aladdin Connect"
    assert len(mock_setup.mock_calls) == 1


async def test_flow_reauth(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
    access_token,
) -> None:
    """Test reauth flow."""
    # Create an existing config entry
    existing_entry = (
        hass.config_entries.async_entries(DOMAIN)[0]
        if hass.config_entries.async_entries(DOMAIN)
        else None
    )
    if not existing_entry:
        existing_entry = MockConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Aladdin Connect",
            data={
                "auth_implementation": DOMAIN,
                "token": {
                    "access_token": "old-token",
                    "refresh_token": "old-refresh-token",
                    "expires_in": 3600,
                    "expires_at": 1234567890,
                },
            },
            source="user",
            unique_id=USER_ID,
        )
        existing_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing_entry.entry_id,
        },
    )

    # Should show reauth confirm form
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    # Confirm reauth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Should now go to user step (OAuth)
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.aladdin_connect.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    # Verify the entry was updated, not a new one created
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_flow_wrong_account_reauth(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
) -> None:
    """Test reauth flow with wrong account."""
    # Create access token for a different user
    different_user_token = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "sub": "different_user_456",
            "aud": [],
            "iat": 1234567890,
            "exp": 1234567890 + 3600,
        },
    )

    # Create an existing config entry with the original user
    existing_entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Aladdin Connect",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old-token",
                "refresh_token": "old-refresh-token",
                "expires_in": 3600,
                "expires_at": 1234567890,
            },
        },
        source="user",
        unique_id=USER_ID,
    )
    existing_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing_entry.entry_id,
        },
    )

    # Confirm reauth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Complete OAuth with different user
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "wrong-user-refresh-token",
            "access_token": different_user_token,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with wrong account
    assert result["type"] == "abort"
    assert result["reason"] == "wrong_account"
