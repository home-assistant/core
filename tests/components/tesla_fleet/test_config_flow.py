"""Test the Tesla Fleet config flow."""

from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from homeassistant.components.tesla_fleet.application_credentials import (
    AUTHORIZE_URL,
    CLIENT_ID,
)
from homeassistant.components.tesla_fleet.const import DOMAIN, SCOPES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

BAD_CONFIG = {CONF_ACCESS_TOKEN: "bad_access_token"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(  # not working
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
    parsed_url = urlparse(result["url"])
    assert parsed_url.netloc == AUTHORIZE_URL
    assert parsed_url.query["response_type"] == "code"
    assert parsed_url.query["client_id"] == CLIENT_ID
    assert (
        parsed_url.query["redirect_uri"] == "https://example.com/auth/external/callback"
    )
    assert parsed_url.query["state"] == state
    assert parsed_url.query["scope"] == " ".join(SCOPES)
    assert parsed_url.query["code_challenge"] is not None

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
        "homeassistant.components.tesla_fleet.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Withings"
    assert "result" in result
    assert result["result"].unique_id == "600"
    assert "token" in result["result"].data
    assert "webhook_id" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
