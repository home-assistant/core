"""Test the Google Mail config flow."""
from unittest.mock import patch

from httplib2 import Response
import pytest

from homeassistant import config_entries
from homeassistant.components.google_mail.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import CLIENT_ID, GOOGLE_AUTH_URI, GOOGLE_TOKEN_URI, SCOPES, TITLE

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "google_mail", context={"source": config_entries.SOURCE_USER}
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
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.google_mail.async_setup_entry", return_value=True
    ) as mock_setup, patch(
        "httplib2.Http.request",
        return_value=(
            Response({}),
            bytes(load_fixture("google_mail/get_profile.json"), encoding="UTF-8"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result.get("type") == "create_entry"
    assert result.get("title") == TITLE
    assert "result" in result
    assert result.get("result").unique_id == TITLE
    assert "token" in result.get("result").data
    assert result.get("result").data["token"].get("access_token") == "mock-access-token"
    assert (
        result.get("result").data["token"].get("refresh_token") == "mock-refresh-token"
    )


@pytest.mark.parametrize(
    ("fixture", "abort_reason", "placeholders", "calls", "access_token"),
    [
        ("get_profile", "reauth_successful", None, 1, "updated-access-token"),
        (
            "get_profile_2",
            "wrong_account",
            {"email": "example@gmail.com"},
            0,
            "mock-access-token",
        ),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host,
    config_entry: MockConfigEntry,
    fixture: str,
    abort_reason: str,
    placeholders: dict[str, str],
    calls: int,
    access_token: str,
) -> None:
    """Test the re-authentication case updates the correct config entry.

    Make sure we abort if the user selects the
    wrong account on the consent screen.
    """
    config_entry.add_to_hass(hass)

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
        f"{GOOGLE_AUTH_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
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
        "homeassistant.components.google_mail.async_setup_entry", return_value=True
    ) as mock_setup, patch(
        "httplib2.Http.request",
        return_value=(
            Response({}),
            bytes(load_fixture(f"google_mail/{fixture}.json"), encoding="UTF-8"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result.get("type") == "abort"
    assert result["reason"] == abort_reason
    assert result["description_placeholders"] == placeholders
    assert len(mock_setup.mock_calls) == calls

    assert config_entry.unique_id == TITLE
    assert "token" in config_entry.data
    # Verify access token is refreshed
    assert config_entry.data["token"].get("access_token") == access_token
    assert config_entry.data["token"].get("refresh_token") == "mock-refresh-token"


async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
    config_entry: MockConfigEntry,
) -> None:
    """Test case where config flow discovers unique id was already configured."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "google_mail", context={"source": config_entries.SOURCE_USER}
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
        f"&state={state}&scope={'+'.join(SCOPES)}"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "httplib2.Http.request",
        return_value=(
            Response({}),
            bytes(load_fixture("google_mail/get_profile.json"), encoding="UTF-8"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") == "abort"
    assert result.get("reason") == "already_configured"
