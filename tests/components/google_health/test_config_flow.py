"""Test the Google Health config flow."""

import pytest

from homeassistant.components.google_health.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OAUTH_SCOPES,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import IDENTITY_URL, USERINFO_URL

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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
        "&scope=https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"
        "+https://www.googleapis.com/auth/googlehealth.profile.readonly"
        "+https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline"
        "&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": " ".join(OAUTH_SCOPES),
        },
    )

    aioclient_mock.get(
        IDENTITY_URL,
        json={
            "name": "users/me/identity",
            "healthUserId": "mock-health-user-id",
            "legacyUserId": "mock-legacy-user-id",
        },
    )

    aioclient_mock.get(
        USERINFO_URL,
        json={
            "sub": "mock-sub",
            "given_name": "Allen",
            "name": "Allen Porter",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Allen"
    assert result["result"].unique_id == "mock-health-user-id"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_missing_profile_scope(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config flow aborts if profile read scope is missing from token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

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

    # Return a token containing only the activity scope (missing profile scope)
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_profile_scope"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_get_identity_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config flow aborts if get_identity raises an API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": " ".join(OAUTH_SCOPES),
        },
    )

    # Mock identity call returning an error
    aioclient_mock.get(IDENTITY_URL, status=500)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_missing_health_user_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config flow aborts if identity does not contain healthUserId."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": " ".join(OAUTH_SCOPES),
        },
    )

    # Return empty healthUserId
    aioclient_mock.get(
        IDENTITY_URL,
        json={
            "name": "users/me/identity",
            "healthUserId": "",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_profile_name_client_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test flow completes with default title if profile userinfo fails with client error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": " ".join(OAUTH_SCOPES),
        },
    )

    aioclient_mock.get(
        IDENTITY_URL,
        json={
            "name": "users/me/identity",
            "healthUserId": "mock-health-user-id",
        },
    )

    # Mock userinfo returning an error
    aioclient_mock.get(USERINFO_URL, status=400)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Health"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_profile_name_unexpected_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test flow completes with default title if profile userinfo raises an unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": " ".join(OAUTH_SCOPES),
        },
    )

    aioclient_mock.get(
        IDENTITY_URL,
        json={
            "name": "users/me/identity",
            "healthUserId": "mock-health-user-id",
        },
    )

    # Return invalid json to trigger JSONDecodeError
    aioclient_mock.get(USERINFO_URL, text="not-json")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Health"
