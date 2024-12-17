"""Tests for the Spotify config flow."""

from http import HTTPStatus
from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest
from spotifyaio import SpotifyConnectionError

from homeassistant.components import zeroconf
from homeassistant.components.spotify.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

BLANK_ZEROCONF_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.2.3.4"),
    ip_addresses=[ip_address("1.2.3.4")],
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={},
    type="mock_type",
)


async def test_abort_if_no_configuration(hass: HomeAssistant) -> None:
    """Check flow aborts when no configuration is present."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=BLANK_ZEROCONF_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


async def test_zeroconf_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check zeroconf flow aborts when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=BLANK_ZEROCONF_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("setup_credentials")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_spotify: MagicMock,
) -> None:
    """Check a full flow."""
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

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://accounts.spotify.com/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=user-modify-playback-state,user-read-playback-state,user-read-private,"
        "playlist-read-private,playlist-read-collaborative,user-library-read,"
        "user-top-read,user-read-playback-position,user-read-recently-played,user-follow-read"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://accounts.spotify.com/api/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch("homeassistant.components.spotify.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1, result

    assert result["type"] is FlowResultType.CREATE_ENTRY
    result["data"]["token"].pop("expires_at")
    assert result["data"]["name"] == "Henk"
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }
    assert result["result"].unique_id == "1112264111"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("setup_credentials")
async def test_abort_if_spotify_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_spotify: MagicMock,
) -> None:
    """Check Spotify errors causes flow to abort."""
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
        "https://accounts.spotify.com/api/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    mock_spotify.return_value.get_current_user.side_effect = SpotifyConnectionError

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "connection_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("setup_credentials")
async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Spotify reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
        "https://accounts.spotify.com/api/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch("homeassistant.components.spotify.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_config_entry.data["token"].pop("expires_at")
    assert mock_config_entry.data["token"] == {
        "refresh_token": "new-refresh-token",
        "access_token": "new-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("setup_credentials")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Spotify reauthentication with different account."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
        "https://accounts.spotify.com/api/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    mock_spotify.return_value.get_current_user.return_value.user_id = (
        "different_user_id"
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"
