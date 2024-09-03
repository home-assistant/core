"""Test the Google Photos config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

from google_photos_library_api.exceptions import GooglePhotosApiError
import pytest

from homeassistant import config_entries
from homeassistant.components.google_photos.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import EXPIRES_IN, FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN, USER_IDENTIFIER

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture(name="mock_setup")
def mock_setup_entry() -> Generator[Mock, None, None]:
    """Fixture to mock out integration setup."""
    with patch(
        "homeassistant.components.google_photos.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(autouse=True)
def mock_patch_api(mock_api: Mock) -> Generator[None, None, None]:
    """Fixture to patch the config flow api."""
    with patch(
        "homeassistant.components.google_photos.config_flow.GooglePhotosLibraryApi",
        return_value=mock_api,
    ):
        yield


@pytest.fixture(name="updated_token_entry", autouse=True)
def mock_updated_token_entry() -> dict[str, Any]:
    """Fixture to provide any test specific overrides to token data from the oauth token endpoint."""
    return {}


@pytest.fixture(name="mock_oauth_token_request", autouse=True)
def mock_token_request(
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, any],
    updated_token_entry: dict[str, Any],
) -> None:
    """Fixture to provide a fake response from the oauth token endpoint."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            **token_entry,
            **updated_token_entry,
        },
    )


@pytest.mark.usefixtures("current_request_with_host", "mock_api")
@pytest.mark.parametrize("fixture_name", ["list_mediaitems.json"])
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup: Mock,
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
        "&scope=https://www.googleapis.com/auth/photoslibrary.readonly"
        "+https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
        "+https://www.googleapis.com/auth/photoslibrary.appendonly"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == USER_IDENTIFIER
    assert config_entry.title == "Test Name"
    config_entry_data = dict(config_entry.data)
    assert "token" in config_entry_data
    assert "expires_at" in config_entry_data["token"]
    del config_entry_data["token"]["expires_at"]
    assert config_entry_data == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": FAKE_ACCESS_TOKEN,
            "expires_in": EXPIRES_IN,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "type": "Bearer",
            "scope": (
                "https://www.googleapis.com/auth/photoslibrary.readonly"
                " https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
                " https://www.googleapis.com/auth/photoslibrary.appendonly"
                " https://www.googleapis.com/auth/userinfo.profile"
            ),
        },
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures(
    "current_request_with_host",
    "setup_credentials",
    "mock_api",
)
@pytest.mark.parametrize(
    "api_error",
    [
        GooglePhotosApiError("some error"),
    ],
)
async def test_api_not_enabled(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Check flow aborts if api is not enabled."""
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
        "&scope=https://www.googleapis.com/auth/photoslibrary.readonly"
        "+https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
        "+https://www.googleapis.com/auth/photoslibrary.appendonly"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "access_not_configured"
    assert result["description_placeholders"]["message"].endswith("some error")


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_general_exception(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_api: Mock,
) -> None:
    """Check flow aborts if exception happens."""
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
        "&scope=https://www.googleapis.com/auth/photoslibrary.readonly"
        "+https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
        "+https://www.googleapis.com/auth/photoslibrary.appendonly"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    mock_api.list_media_items.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host", "mock_api", "setup_integration")
@pytest.mark.parametrize("fixture_name", ["list_mediaitems.json"])
@pytest.mark.parametrize(
    "updated_token_entry",
    [
        {
            "access_token": "updated-access-token",
        }
    ],
)
@pytest.mark.parametrize(
    (
        "user_identifier",
        "abort_reason",
        "resulting_access_token",
        "expected_setup_calls",
    ),
    [
        (
            USER_IDENTIFIER,
            "reauth_successful",
            "updated-access-token",
            1,
        ),
        (
            "345",
            "wrong_account",
            FAKE_ACCESS_TOKEN,
            0,
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    user_identifier: str,
    abort_reason: str,
    resulting_access_token: str,
    mock_setup: Mock,
    expected_setup_calls: int,
) -> None:
    """Test the re-authentication case updates the correct config entry."""

    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
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
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=https://www.googleapis.com/auth/photoslibrary.readonly"
        "+https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
        "+https://www.googleapis.com/auth/photoslibrary.appendonly"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline&prompt=consent"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason

    assert config_entry.unique_id == USER_IDENTIFIER
    assert config_entry.title == "Account Name"
    config_entry_data = dict(config_entry.data)
    assert "token" in config_entry_data
    assert "expires_at" in config_entry_data["token"]
    del config_entry_data["token"]["expires_at"]
    assert config_entry_data == {
        "auth_implementation": DOMAIN,
        "token": {
            # Verify token is refreshed or not
            "access_token": resulting_access_token,
            "expires_in": EXPIRES_IN,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "type": "Bearer",
            "scope": (
                "https://www.googleapis.com/auth/photoslibrary.readonly"
                " https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata"
                " https://www.googleapis.com/auth/photoslibrary.appendonly"
                " https://www.googleapis.com/auth/userinfo.profile"
            ),
        },
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == expected_setup_calls
