"""Tests for the Spotify config flow."""
from http import HTTPStatus
from unittest.mock import patch

import pytest
from spotipy import SpotifyException

from homeassistant import data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.spotify.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

BLANK_ZEROCONF_INFO = zeroconf.ZeroconfServiceInfo(
    host="1.2.3.4",
    addresses=["1.2.3.4"],
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={},
    type="mock_type",
)


@pytest.fixture
async def component_setup(hass: HomeAssistant) -> None:
    """Fixture for setting up the integration."""
    result = await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client", "secret"), "cred"
    )

    assert result


async def test_abort_if_no_configuration(hass: HomeAssistant) -> None:
    """Check flow aborts when no configuration is present."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=BLANK_ZEROCONF_INFO
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


async def test_zeroconf_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check zeroconf flow aborts when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=BLANK_ZEROCONF_INFO
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow(
    hass: HomeAssistant,
    component_setup,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
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

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://accounts.spotify.com/authorize"
        "?response_type=code&client_id=client"
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

    aioclient_mock.post(
        "https://accounts.spotify.com/api/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.spotify.async_setup_entry", return_value=True
    ), patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        spotify_mock.return_value.current_user.return_value = {
            "id": "fake_id",
            "display_name": "frenck",
        }
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == "cred"
    result["data"]["token"].pop("expires_at")
    assert result["data"]["name"] == "frenck"
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


async def test_abort_if_spotify_error(
    hass: HomeAssistant,
    component_setup,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
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

    with patch(
        "homeassistant.components.spotify.config_flow.Spotify.current_user",
        side_effect=SpotifyException(400, -1, "message"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "connection_error"


async def test_reauthentication(
    hass: HomeAssistant,
    component_setup,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Test Spotify reauthentication."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=123,
        version=1,
        data={"id": "frenck", "auth_implementation": "cred"},
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

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

    with patch(
        "homeassistant.components.spotify.async_setup_entry", return_value=True
    ), patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        spotify_mock.return_value.current_user.return_value = {"id": "frenck"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == "cred"
    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    component_setup,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Test Spotify reauthentication with different account."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=123,
        version=1,
        data={"id": "frenck", "auth_implementation": "cred"},
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    flows = hass.config_entries.flow.async_progress()
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

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

    with patch("homeassistant.components.spotify.config_flow.Spotify") as spotify_mock:
        spotify_mock.return_value.current_user.return_value = {"id": "fake_id"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


async def test_abort_if_no_reauth_entry(hass: HomeAssistant) -> None:
    """Check flow aborts when no entry is known when entring reauth confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth_confirm"}
    )

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "reauth_account_mismatch"
