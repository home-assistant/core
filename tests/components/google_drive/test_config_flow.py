"""Test the Google Drive config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from google_drive_api.exceptions import GoogleDriveApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_drive.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import CLIENT_ID, TEST_USER_EMAIL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
FOLDER_ID = "google-folder-id"
FOLDER_NAME = "folder name"
TITLE = "Google Drive"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
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
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=https://www.googleapis.com/auth/drive.file"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    # Prepare API responses
    mock_api.get_user = AsyncMock(
        return_value={"user": {"emailAddress": TEST_USER_EMAIL}}
    )
    mock_api.list_files = AsyncMock(return_value={"files": []})
    mock_api.create_file = AsyncMock(
        return_value={"id": FOLDER_ID, "name": FOLDER_NAME}
    )

    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.google_drive.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(aioclient_mock.mock_calls) == 1
    assert [tuple(mock_call) for mock_call in mock_api.mock_calls] == snapshot

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == TITLE
    assert result.get("description_placeholders") == {
        "folder_name": FOLDER_NAME,
        "url": f"https://drive.google.com/drive/folders/{FOLDER_ID}",
    }
    assert "result" in result
    assert result.get("result").unique_id == TEST_USER_EMAIL
    assert "token" in result.get("result").data
    assert result.get("result").data["token"].get("access_token") == "mock-access-token"
    assert (
        result.get("result").data["token"].get("refresh_token") == "mock-refresh-token"
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_create_folder_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: MagicMock,
) -> None:
    """Test case where creating the folder fails."""
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
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=https://www.googleapis.com/auth/drive.file"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    # Prepare API responses
    mock_api.get_user = AsyncMock(
        return_value={"user": {"emailAddress": TEST_USER_EMAIL}}
    )
    mock_api.list_files = AsyncMock(return_value={"files": []})
    mock_api.create_file = AsyncMock(side_effect=GoogleDriveApiError("some error"))

    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "create_folder_failure"
    assert result.get("description_placeholders") == {"message": "some error"}


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("exception", "expected_abort_reason", "expected_placeholders"),
    [
        (
            GoogleDriveApiError("some error"),
            "access_not_configured",
            {"message": "some error"},
        ),
        (Exception, "unknown", None),
    ],
    ids=["api_not_enabled", "general_exception"],
)
async def test_get_email_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_api: MagicMock,
    exception: Exception,
    expected_abort_reason,
    expected_placeholders,
) -> None:
    """Test case where getting the email address fails."""
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
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=https://www.googleapis.com/auth/drive.file"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    # Prepare API responses
    mock_api.get_user = AsyncMock(side_effect=exception)
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == expected_abort_reason
    assert result.get("description_placeholders") == expected_placeholders


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    (
        "new_email",
        "expected_abort_reason",
        "expected_placeholders",
        "expected_access_token",
        "expected_setup_calls",
    ),
    [
        (TEST_USER_EMAIL, "reauth_successful", None, "updated-access-token", 1),
        (
            "other.user@domain.com",
            "wrong_account",
            {"email": TEST_USER_EMAIL},
            "mock-access-token",
            0,
        ),
    ],
    ids=["reauth_successful", "wrong_account"],
)
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_api: MagicMock,
    new_email: str,
    expected_abort_reason: str,
    expected_placeholders: dict[str, str] | None,
    expected_access_token: str,
    expected_setup_calls: int,
) -> None:
    """Test the reauthentication flow."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["url"] == (
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=https://www.googleapis.com/auth/drive.file"
        "&access_type=offline&prompt=consent"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    # Prepare API responses
    mock_api.get_user = AsyncMock(return_value={"user": {"emailAddress": new_email}})
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "updated-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.google_drive.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == expected_setup_calls

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == expected_abort_reason
    assert result.get("description_placeholders") == expected_placeholders

    assert config_entry.unique_id == TEST_USER_EMAIL
    assert "token" in config_entry.data

    # Verify access token is refreshed
    assert config_entry.data["token"].get("access_token") == expected_access_token
    assert config_entry.data["token"].get("refresh_token") == "mock-refresh-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_api: MagicMock,
) -> None:
    """Test already configured account."""
    config_entry.add_to_hass(hass)

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
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=https://www.googleapis.com/auth/drive.file"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    # Prepare API responses
    mock_api.get_user = AsyncMock(
        return_value={"user": {"emailAddress": TEST_USER_EMAIL}}
    )
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
