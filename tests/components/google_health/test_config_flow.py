"""Test the Google Health config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_health.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OAUTH_SCOPES,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .conftest import IDENTITY_URL, USERINFO_URL

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
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

    with patch(
        "homeassistant.components.google_health.async_setup_entry", return_value=True
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Allen"
    assert result2["result"].unique_id == "mock-health-user-id"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_flow_missing_profile_scope(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test config flow aborts if profile read scope is missing from token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "missing_profile_scope"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_flow_get_identity_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test config flow aborts if get_identity raises an API error."""
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

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_flow_missing_health_user_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test config flow aborts if identity does not contain healthUserId."""
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

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_flow_profile_name_client_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test flow completes with default title if profile userinfo fails with client error."""
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

    with patch(
        "homeassistant.components.google_health.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Google Health"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_flow_profile_name_unexpected_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test flow completes with default title if profile userinfo raises an unexpected error."""
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

    with patch(
        "homeassistant.components.google_health.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Google Health"
