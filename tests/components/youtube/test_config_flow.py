"""Test the YouTube config flow."""
from unittest.mock import patch

import pytest
from youtubeaio.types import ForbiddenError

from homeassistant import config_entries
from homeassistant.components.youtube.const import CONF_CHANNELS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import MockYouTube
from .conftest import (
    CLIENT_ID,
    GOOGLE_AUTH_URI,
    GOOGLE_TOKEN_URI,
    SCOPES,
    TITLE,
    ComponentSetup,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "youtube", context={"source": config_entries.SOURCE_USER}
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
        "homeassistant.components.youtube.async_setup_entry", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.youtube.config_flow.YouTube",
        return_value=MockYouTube(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "channels"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_CHANNELS: ["UC_x5XG1OV2P6uZZ5FSM9Ttw"]}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] == "create_entry"
    assert result["title"] == TITLE
    assert "result" in result
    assert result["result"].unique_id == "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["options"] == {CONF_CHANNELS: ["UC_x5XG1OV2P6uZZ5FSM9Ttw"]}


async def test_flow_abort_without_channel(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check abort flow if user has no channel."""
    result = await hass.config_entries.flow.async_init(
        "youtube", context={"source": config_entries.SOURCE_USER}
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

    service = MockYouTube(channel_fixture="youtube/get_no_channel.json")
    with patch(
        "homeassistant.components.youtube.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.youtube.config_flow.YouTube", return_value=service
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_channel"


async def test_flow_abort_without_subscriptions(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check abort flow if user has no subscriptions."""
    result = await hass.config_entries.flow.async_init(
        "youtube", context={"source": config_entries.SOURCE_USER}
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

    service = MockYouTube(subscriptions_fixture="youtube/get_no_subscriptions.json")
    with patch(
        "homeassistant.components.youtube.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.youtube.config_flow.YouTube", return_value=service
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_subscriptions"


async def test_flow_http_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "youtube", context={"source": config_entries.SOURCE_USER}
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
        "homeassistant.components.youtube.config_flow.YouTube.get_user_channels",
        side_effect=ForbiddenError(
            "YouTube Data API v3 has not been used in project 0 before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/youtube.googleapis.com/overview?project=0 then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry."
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "access_not_configured"
        assert result["description_placeholders"]["message"] == (
            "YouTube Data API v3 has not been used in project 0 before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/youtube.googleapis.com/overview?project=0 then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry."
        )


@pytest.mark.parametrize(
    ("fixture", "abort_reason", "placeholders", "calls", "access_token"),
    [
        (
            "get_channel",
            "reauth_successful",
            None,
            1,
            "updated-access-token",
        ),
        (
            "get_channel_2",
            "wrong_account",
            {"title": "Linus Tech Tips"},
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

    youtube = MockYouTube(channel_fixture=f"youtube/{fixture}.json")
    with patch(
        "homeassistant.components.youtube.async_setup_entry", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.youtube.config_flow.YouTube",
        return_value=youtube,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert result["type"] == "abort"
    assert result["reason"] == abort_reason
    assert result["description_placeholders"] == placeholders
    assert len(mock_setup.mock_calls) == calls

    assert config_entry.unique_id == "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    assert "token" in config_entry.data
    # Verify access token is refreshed
    assert config_entry.data["token"]["access_token"] == access_token
    assert config_entry.data["token"]["refresh_token"] == "mock-refresh-token"


async def test_flow_exception(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "youtube", context={"source": config_entries.SOURCE_USER}
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
        "homeassistant.components.youtube.config_flow.YouTube", side_effect=Exception
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_options_flow(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test the full options flow."""
    await setup_integration()
    with patch(
        "homeassistant.components.youtube.config_flow.YouTube",
        return_value=MockYouTube(),
    ):
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_CHANNELS: ["UC_x5XG1OV2P6uZZ5FSM9Ttw"]},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {CONF_CHANNELS: ["UC_x5XG1OV2P6uZZ5FSM9Ttw"]}
