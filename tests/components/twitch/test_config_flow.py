"""Test config flow for Twitch."""
from unittest.mock import patch

import pytest

from homeassistant.components.twitch.const import CONF_CHANNELS, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.components.twitch import TwitchMock
from tests.components.twitch.conftest import (
    CLIENT_ID,
    SCOPES,
    TWITCH_AUTHORIZE_URI,
)
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "twitch", context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{TWITCH_AUTHORIZE_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.twitch.async_setup_entry", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.twitch.sensor.Twitch", return_value=TwitchMock()
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch", return_value=TwitchMock()
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "channels"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CHANNELS: ["internetofthings"]}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] == "create_entry"
    assert result["title"] == "channel123"
    assert "result" in result
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["options"] == {CONF_CHANNELS: ["internetofthings"]}


async def test_user_not_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Test if the user can't be found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{TWITCH_AUTHORIZE_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch",
        return_value=TwitchMock(user_found=False),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == FlowResultType.ABORT
        assert result.get("reason") == "user_not_found"


@pytest.mark.parametrize(
    ("abort_reason", "different_user_id", "placeholders", "access_token"),
    [
        ("reauth_successful", False, None, "updated-access-token"),
        (
            "wrong_account",
            True,
            {"username": "Test"},
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
    abort_reason: str,
    different_user_id: bool,
    placeholders: dict[str, str],
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
        f"{TWITCH_AUTHORIZE_URI}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={'+'.join(SCOPES)}"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://id.twitch.tv/oauth2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "updated-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch",
        return_value=TwitchMock(different_user_id=different_user_id),
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result["type"] == "abort"
    assert result["reason"] == abort_reason
    assert result["description_placeholders"] == placeholders
    assert len(mock_setup.mock_calls) == 1

    assert config_entry.unique_id == "123"
    assert "token" in config_entry.data
    # Verify access token is refreshed
    assert config_entry.data["token"]["access_token"] == access_token
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"
