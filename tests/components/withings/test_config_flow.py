"""Tests for config flow."""
from unittest.mock import patch

from homeassistant.components.withings.const import DOMAIN, PROFILE
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import CLIENT_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
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

    assert result["type"] == FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://account.withings.com/oauth2_user/authorize2?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
        "&scope=user.info,user.metrics,user.activity,user.sleepevents"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://wbsapi.withings.net/v2/oauth2",
        json={
            "body": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": 600,
            },
        },
    )
    with patch(
        "homeassistant.components.withings.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "profile"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={PROFILE: "Henk"}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Henk"
    assert "result" in result
    assert result["result"].unique_id == "600"
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"


async def test_config_non_unique_profile(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup a non-unique profile."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={PROFILE: "Henk"}, unique_id="0")
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

    assert result["type"] == FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://account.withings.com/oauth2_user/authorize2?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
        "&scope=user.info,user.metrics,user.activity,user.sleepevents"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://wbsapi.withings.net/v2/oauth2",
        json={
            "body": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": 10,
            },
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "profile"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={PROFILE: "Henk"}
    )

    assert result
    assert result["errors"]["base"] == "already_configured"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={PROFILE: "Henk 2"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Henk 2"
    assert "result" in result
    assert result["result"].unique_id == "10"


async def test_config_reauth_profile(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    current_request_with_host,
) -> None:
    """Test reauth an existing profile re-creates the config entry."""
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
        "https://account.withings.com/oauth2_user/authorize2?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
        "&scope=user.info,user.metrics,user.activity,user.sleepevents"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://wbsapi.withings.net/v2/oauth2",
        json={
            "body": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": "0",
            },
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["token"]["refresh_token"] == "mock-refresh-token"
