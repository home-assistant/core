"""Test the Geocaching config flow."""
from unittest.mock import patch

from geocachingapi import GeocachingStatus

from homeassistant import config_entries, setup
from homeassistant.components.geocaching.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE_URL,
    OAUTH2_TOKEN_URL,
)
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
REDIRECT_URI = "https://example.com/auth/external/callback"


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        "geocaching",
        {
            "geocaching": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "geocaching", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE_URL}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}&scope=*"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    test_status = GeocachingStatus()
    test_status.user.username = "mock_user"

    with patch(
        "homeassistant.components.geocaching.async_setup_entry", return_value=True
    ) as mock_setup:
        with patch("geocachingapi.GeocachingApi.update", return_value=test_status):
            await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_existing_entry(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check existing entry."""
    MockConfigEntry(domain=DOMAIN, unique_id="mock_user").add_to_hass(hass)
    await setup.async_setup_component(
        hass,
        "geocaching",
        {
            "geocaching": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "geocaching", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    test_status = GeocachingStatus()
    test_status.user.username = "mock_user"

    with patch(
        "homeassistant.components.geocaching.async_setup_entry", return_value=True
    ):
        with patch("geocachingapi.GeocachingApi.update", return_value=test_status):
            await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauthentication(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Test Geocaching reauthentication."""
    await setup.async_setup_component(
        hass,
        "geocaching",
        {
            "geocaching": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "geocaching", context={"source": config_entries.SOURCE_REAUTH}
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await aiohttp_client(hass.http.app)
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    test_status = GeocachingStatus()
    test_status.user.username = "mock_user"

    with patch(
        "homeassistant.components.geocaching.async_setup_entry", return_value=True
    ) as mock_setup:
        with patch("geocachingapi.GeocachingApi.update", return_value=test_status):
            await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
