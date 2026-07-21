"""Test the Google Health config flow."""

from unittest.mock import AsyncMock, patch

from google_health_api.const import HealthApiScope
from google_health_api.exceptions import (
    GoogleHealthApiError,
    HealthApiForbiddenException,
)
from google_health_api.model import Identity
import pytest

from homeassistant import config_entries
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

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

API_BASE_URL = "https://health.googleapis.com/v4/users/me"
IDENTITY_URL = f"{API_BASE_URL}/identity"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.mark.usefixtures(
    "current_request_with_host",
    "mock_setup_entry",
    "setup_credentials",
    "mock_google_health_client",
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
        "+https://www.googleapis.com/auth/googlehealth.sleep.readonly"
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test"
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
    mock_google_health_client: AsyncMock,
) -> None:
    """Test config flow aborts if get_identity raises an API error."""
    mock_google_health_client.get_identity.side_effect = GoogleHealthApiError

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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_api_not_enabled(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_google_health_client: AsyncMock,
) -> None:
    """Test config flow aborts if the Google Health API is not enabled."""
    mock_google_health_client.get_identity.side_effect = HealthApiForbiddenException

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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_not_enabled"
    assert result["description_placeholders"] == {
        "url": "https://console.developers.google.com/apis/api/health.googleapis.com/overview"
    }


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_missing_health_user_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_google_health_client: AsyncMock,
) -> None:
    """Test config flow aborts if identity does not contain healthUserId."""
    mock_google_health_client.get_identity.return_value = Identity(
        name="users/me/identity", health_user_id=""
    )

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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "setup_credentials"
)
async def test_config_flow_profile_name_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_google_health_client: AsyncMock,
) -> None:
    """Test flow completes with default title if fetching profile userinfo fails."""
    mock_google_health_client.get_user_info.side_effect = GoogleHealthApiError

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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Health"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test reauth flow completes successfully."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "google",
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "scope": " ".join(OAUTH_SCOPES),
            },
        },
        unique_id="mock-health-user-id",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
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
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
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

    aioclient_mock.get(
        USERINFO_URL,
        json={
            "givenName": "Test",
            "name": "Test User",
        },
    )

    with patch(
        "homeassistant.components.google_health.async_setup_entry", return_value=True
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    assert config_entry.data["token"]["access_token"] == "new-access-token"
    assert config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test reconfigure flow completes successfully."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "google",
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "scope": HealthApiScope.PROFILE_READ,
            },
        },
        unique_id="mock-health-user-id",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
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
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
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

    aioclient_mock.get(
        USERINFO_URL,
        json={
            "givenName": "Test",
            "name": "Test User",
        },
    )

    with patch(
        "homeassistant.components.google_health.async_setup_entry", return_value=True
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    assert config_entry.data["token"]["access_token"] == "new-access-token"
    assert config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    assert config_entry.data["token"]["scope"] == " ".join(OAUTH_SCOPES)
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_reconfigure_flow_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test reconfigure flow aborts if the wrong account is authenticated."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "google",
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "scope": " ".join(OAUTH_SCOPES),
            },
        },
        unique_id="mock-health-user-id",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
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
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": " ".join(OAUTH_SCOPES),
        },
    )

    aioclient_mock.get(
        IDENTITY_URL,
        json={
            "name": "users/me/identity",
            "healthUserId": "wrong-health-user-id",
        },
    )

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"
